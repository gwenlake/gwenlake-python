"""Foundry-style transforms over the Gwenlake catalog.

Mirrors the Palantir Foundry ``transforms.api`` ergonomics on top of the
Gwenlake client:

    from gwenlake.transforms import transform_df, Input, Output

    @transform_df(
        donnees_brutes=Input("Projet_A.utilisateurs"),
        donnees_nettoyees=Output("Projet_A.utilisateurs_filtres"),
    )
    def ma_transformation(donnees_brutes):
        return donnees_brutes[donnees_brutes.age >= 18].assign(
            nom_majuscule=lambda d: d.nom.str.upper()
        )

    ma_transformation(client)   # reads, computes, writes

Three decorators are provided:

* ``transform_df`` — the decorated function receives each ``Input`` as a
  ``pandas.DataFrame`` (matched by keyword name) and **returns** a single
  DataFrame which is written to the (single) ``Output``.
* ``transform`` — the lower-level form: the function receives ``TransformInput``
  and ``TransformOutput`` objects (matched by keyword name). Call
  ``.dataframe()`` to read, ``.write_dataframe(df)`` to write, and
  ``.filesystem()`` for raw file access (images, PDFs, anything non-tabular).
* ``train`` — produces a **model** instead of a dataset: its ``Output`` names a
  model, and the function writes the fitted artifacts under ``output.path``
  (the model's directory in the repository checkout). The build engine commits
  them and pins that commit as the model's version.

A third reference, ``Model("<project>.<model>")``, binds a model a transform
*loads* — conventionally as ``model=Model(...)``. It arrives as a
``TransformModel`` whose ``path`` points at the artifacts on disk. Models live
in the same repository as the code that trains or predicts with them.

Datasets are addressed as ``"<project_alias>.<dataset_alias>"`` — the same
handle DuckDB uses in ``FROM '<project>.<dataset>'``. A bare string with no dot
is treated as a dataset alias (searched across datasets) or, failing that, as a
dataset id.

``pandas`` and ``pyarrow`` are included in the base install.
"""

import functools
import inspect
import io
import os
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

from gwenlake.exceptions import GwenlakeException


# Rows per page when reading/writing a dataset in chunks (LIMIT/OFFSET).
DEFAULT_CHUNK_SIZE = 50_000


# ---------------------------------------------------------------------------
# Dataset reference specs (what the user writes inside the decorator)
# ---------------------------------------------------------------------------

class _DatasetRef:
    """A dataset reference, e.g. ``"Projet_A.utilisateurs"`` or a dataset id."""

    def __init__(self, ref: str):
        if not isinstance(ref, str) or not ref:
            raise ValueError("Input/Output expects a non-empty 'project_alias.dataset_alias' string")
        self.ref = ref

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"{type(self).__name__}({self.ref!r})"


class Input(_DatasetRef):
    """References an input dataset for a transform."""


class Output(_DatasetRef):
    """References what a transform produces: the output dataset of a
    ``transform``/``transform_df``, or the **model** of a ``train``."""


class Model(_DatasetRef):
    """References a model the transform loads, e.g. ``Model("crm.churn")``.

    Conventionally bound to the ``model=`` keyword. The decorated function
    receives a :class:`TransformModel` — use ``model.path`` to read the
    artifacts, which live in the same repository as this code.
    """


# ---------------------------------------------------------------------------
# Resolution & IO helpers
# ---------------------------------------------------------------------------

def _resolve_dataset_id(client: Any, ref: str) -> str:
    """Resolve ``"<project_alias>.<dataset_alias>"`` (or a bare alias / id) to a
    dataset id, using the client's ``projects`` and ``datasets`` resources."""
    if "." in ref:
        project_alias, dataset_alias = ref.split(".", 1)
        project = next((p for p in client.projects.list() if p.get("alias") == project_alias), None)
        if project is None:
            raise GwenlakeException(f"No project with alias '{project_alias}' (in ref '{ref}')")
        datasets = client.datasets.list(project_id=project["id"])
        dataset = next((d for d in datasets if d.get("alias") == dataset_alias), None)
        if dataset is None:
            raise GwenlakeException(f"No dataset '{dataset_alias}' in project '{project_alias}'")
        return dataset["id"]

    # No dot: try as a dataset alias across all datasets, else assume it's an id.
    match = next((d for d in client.datasets.list() if d.get("alias") == ref), None)
    return match["id"] if match else ref


def _require_pandas():
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise GwenlakeException(
            "pandas is required for transforms; install with: pip install gwenlake"
        ) from exc
    return pd


def _catalog_branch() -> Optional[str]:
    """The Iceberg data branch a build targets, from the `CATALOG_BRANCH` env the
    build engine sets. ``None`` on trunk (unset / "main"), so reads and writes
    stay on the default version outside a branch build."""
    branch = os.environ.get("CATALOG_BRANCH", "").strip()
    return branch if branch and branch != "main" else None


def _is_iceberg(client: Any, dataset_id: str) -> bool:
    """Whether the dataset is Iceberg-backed (so writes go through the table, not
    the raw file store). Best-effort: any lookup failure assumes files."""
    try:
        ds = client.datasets.get(dataset_id)
        info = ds if isinstance(ds, dict) else getattr(ds, "__dict__", {})
        return (info or {}).get("type") == "iceberg"
    except Exception:
        return False


def _sql_table(client: Any, ref: str) -> str:
    """The '<project>.<dataset>' table handle DuckDB uses in FROM, from a ref.

    On a branch build (`CATALOG_BRANCH` set), the `:branch` suffix is appended so
    the read resolves that Iceberg branch — the same `project.dataset:branch`
    syntax `/sql` understands. Non-Iceberg inputs ignore it server-side."""
    handle = ref if "." in ref else _ref_to_sql_table(client, ref)
    branch = _catalog_branch()
    return f"{handle}:{branch}" if branch else handle


def _run_rows(client: Any, statement: str) -> List[Dict[str, Any]]:
    """Run a SQL statement and return its rows (the ``data`` list)."""
    result = client.statements.create(statement=statement, format="json")
    return result.get("data", []) if isinstance(result, dict) else (result or [])


def _iter_row_pages(
    client: Any,
    table: str,
    chunk_size: int,
    order_by: Optional[str] = None,
) -> Iterator[List[Dict[str, Any]]]:
    """Yield successive pages of rows via ``LIMIT/OFFSET`` until exhausted.

    Without an ``order_by`` the page boundaries rely on the engine's scan order,
    which DuckDB keeps stable for a static dataset; pass ``order_by`` (e.g. a
    primary key) for a guaranteed-deterministic split.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    order = f" ORDER BY {order_by}" if order_by else ""
    offset = 0
    while True:
        rows = _run_rows(
            client,
            f"SELECT * FROM '{table}'{order} LIMIT {chunk_size} OFFSET {offset}",
        )
        if not rows:
            break
        yield rows
        if len(rows) < chunk_size:
            break
        offset += chunk_size


def _iter_dataframes(
    client: Any,
    ref: str,
    chunk_size: int,
    order_by: Optional[str] = None,
) -> Iterator[Any]:
    """Yield the dataset as successive ``pandas.DataFrame`` chunks."""
    pd = _require_pandas()
    table = _sql_table(client, ref)
    for rows in _iter_row_pages(client, table, chunk_size, order_by):
        yield pd.DataFrame(rows)


def _read_dataframe(
    client: Any,
    ref: str,
    *,
    chunk_size: Optional[int] = None,
    order_by: Optional[str] = None,
):
    """Read a dataset into a single ``pandas.DataFrame``.

    With ``chunk_size=None`` (default) it issues one ``SELECT *``. Pass a
    ``chunk_size`` to page through with ``LIMIT/OFFSET`` and concatenate — same
    result, but bounded request/response sizes for very large datasets.
    """
    pd = _require_pandas()
    if chunk_size is None:
        table = _sql_table(client, ref)
        return pd.DataFrame(_run_rows(client, f"SELECT * FROM '{table}'"))
    chunks = list(_iter_dataframes(client, ref, chunk_size, order_by))
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def _serialize_df(df: Any, format: str) -> Tuple[bytes, str]:
    """Serialize a DataFrame to bytes; returns (bytes, default_extension)."""
    if not hasattr(df, "to_parquet"):
        raise TypeError(f"expected a pandas.DataFrame, got {type(df).__name__}")
    buf = io.BytesIO()
    if format == "csv":
        df.to_csv(buf, index=False)
        return buf.getvalue(), "csv"
    if format == "parquet":
        df.to_parquet(buf, index=False)
        return buf.getvalue(), "parquet"
    raise ValueError(f"Unsupported format '{format}' (use 'parquet' or 'csv')")


def _ref_to_sql_table(client: Any, ref: str) -> str:
    """Best-effort: turn a bare dataset alias/id into '<project>.<dataset>'."""
    datasets = client.datasets.list()
    ds = next((d for d in datasets if d.get("alias") == ref or d.get("id") == ref), None)
    if ds is None:
        return ref
    projects = {p["id"]: p["alias"] for p in client.projects.list()}
    project_alias = projects.get(ds.get("parent_id"))
    return f"{project_alias}.{ds['alias']}" if project_alias else ds["alias"]


def _split_path(filepath: str) -> Tuple[Optional[str], str]:
    """Split ``"a/b/c.pdf"`` into (path="a/b", filename="c.pdf")."""
    path, filename = os.path.split(filepath)
    return (path or None), filename


def _entry_path(entry: Any) -> Optional[str]:
    """Extract the usable file path from a ``files.list`` entry."""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        path = entry.get("path")
        name = entry.get("filename") or entry.get("name") or entry.get("key")
        if name and path and not name.startswith(path):
            return f"{path.rstrip('/')}/{name}"
        return name or path
    return None


def _is_directory(entry: Any) -> bool:
    """Whether a ``files.list`` entry denotes a folder rather than a file."""
    if not isinstance(entry, dict):
        return False
    kind = (entry.get("type") or entry.get("object") or "").lower()
    if kind in ("directory", "folder", "dir", "prefix"):
        return True
    if entry.get("is_dir") or entry.get("is_directory"):
        return True
    # A leaf with a size is a file; a name ending in "/" is a folder.
    name = _entry_path(entry) or ""
    return name.endswith("/") and "file_size" not in entry and "size" not in entry


# ---------------------------------------------------------------------------
# Raw file access (images, PDFs, anything non-tabular)
# ---------------------------------------------------------------------------

class _WriteBuffer(io.BytesIO):
    """A writable byte buffer that uploads its contents to the dataset on close,
    so ``with fs.open("out.pdf", "wb") as f: f.write(data)`` works."""

    def __init__(self, fs: "FileSystem", filepath: str):
        super().__init__()
        self._fs = fs
        self._filepath = filepath
        self._uploaded = False

    def close(self) -> None:
        if not self._uploaded and not self.closed:
            self._uploaded = True
            self._fs.write(self._filepath, self.getvalue())
        super().close()

    def __enter__(self) -> "_WriteBuffer":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class FileSystem:
    """Raw S3-backed file access for a dataset, mirroring Foundry's FileSystem."""

    def __init__(self, client: Any, dataset_id: str):
        self._client = client
        self._dataset_id = dataset_id

    def ls(self, path: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files in the dataset (optionally under ``path``)."""
        return self._client.files.list(self._dataset_id, path=path)

    # Foundry alias
    files = ls

    def read(self, filepath: str) -> bytes:
        """Download a file's raw bytes."""
        return self._client.files.download(self._dataset_id, filepath)

    def write(
        self,
        filepath: str,
        data: bytes,
        *,
        mode: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload raw bytes to ``filepath`` within the dataset. ``mode``
        (APPEND/SNAPSHOT) and ``branch`` steer Iceberg writes; files datasets
        ignore them."""
        path, filename = _split_path(filepath)
        return self._client.files.upload(
            self._dataset_id, data, path=path, filename=filename, mode=mode, branch=branch
        )

    def delete(self, filepath: str) -> bool:
        """Delete a single file from the dataset."""
        return self._client.files.delete(self._dataset_id, filepath)

    def clear(self, path: Optional[str] = None) -> int:
        """Delete every file in the dataset (recursively, descending into any
        sub-folders); returns the number removed. Emulates Foundry's snapshot
        (replace) write semantics."""
        removed = 0
        for entry in self.ls(path) or []:
            filepath = _entry_path(entry)
            if not filepath or filepath.rstrip("/") == (path or "").rstrip("/"):
                continue
            if _is_directory(entry):
                removed += self.clear(filepath.rstrip("/"))
            else:
                self.delete(filepath)
                removed += 1
        return removed

    def open(self, filepath: str, mode: str = "r"):
        """Open a file. Read modes return a ``BytesIO`` of the downloaded bytes;
        write modes return a buffer that uploads to ``filepath`` on close."""
        if "w" in mode or "a" in mode:
            return _WriteBuffer(self, filepath)
        return io.BytesIO(self.read(filepath))


# ---------------------------------------------------------------------------
# Transform IO objects (passed to @transform functions)
# ---------------------------------------------------------------------------

class TransformInput:
    """An input dataset handle. Use ``.dataframe()`` for tabular data or
    ``.filesystem()`` for raw files."""

    def __init__(self, client: Any, ref: str):
        self._client = client
        self.ref = ref
        self._dataset_id: Optional[str] = None

    @property
    def dataset_id(self) -> str:
        if self._dataset_id is None:
            self._dataset_id = _resolve_dataset_id(self._client, self.ref)
        return self._dataset_id

    def dataframe(self, *, chunk_size: Optional[int] = None, order_by: Optional[str] = None):
        """Read the whole dataset into a ``pandas.DataFrame``.

        With ``chunk_size`` set, pages through with ``LIMIT/OFFSET`` and
        concatenates (bounded request sizes); without it, one ``SELECT *``.
        """
        return _read_dataframe(self._client, self.ref, chunk_size=chunk_size, order_by=order_by)

    def iter_dataframes(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        order_by: Optional[str] = None,
    ) -> Iterator[Any]:
        """Iterate over the dataset as ``pandas.DataFrame`` chunks of ``chunk_size``
        rows — for datasets too large to hold in memory at once."""
        return _iter_dataframes(self._client, self.ref, chunk_size, order_by)

    def filesystem(self) -> FileSystem:
        return FileSystem(self._client, self.dataset_id)


class TransformOutput:
    """An output dataset handle. Use ``.write_dataframe(df)`` for tabular data or
    ``.filesystem()`` for raw files."""

    def __init__(self, client: Any, ref: str):
        self._client = client
        self.ref = ref
        self._dataset_id: Optional[str] = None

    @property
    def dataset_id(self) -> str:
        if self._dataset_id is None:
            self._dataset_id = _resolve_dataset_id(self._client, self.ref)
        return self._dataset_id

    def write_dataframe(
        self,
        df: Any,
        *,
        filename: str = "data.parquet",
        format: str = "parquet",
        mode: str = "replace",
    ) -> Dict[str, Any]:
        """Write a ``pandas.DataFrame`` to the dataset as a single file.

        ``mode="replace"`` (default) clears the dataset's existing files first,
        emulating Foundry's snapshot write; ``mode="append"`` just adds the file
        alongside whatever is already there. ``format`` is ``"parquet"`` (default)
        or ``"csv"``.
        """
        if mode not in ("replace", "append"):
            raise ValueError(f"Unsupported mode '{mode}' (use 'replace' or 'append')")
        data, ext = _serialize_df(df, format)
        if filename == "data.parquet" and ext != "parquet":
            filename = f"data.{ext}"
        fs = self.filesystem()
        branch = _catalog_branch()
        if _is_iceberg(self._client, self.dataset_id):
            # The server writes into the Iceberg table on `branch`: SNAPSHOT
            # overwrites it (replace), APPEND adds to it. Never touch the table's
            # physical files directly.
            wire_mode = "SNAPSHOT" if mode == "replace" else "APPEND"
            return fs.write(filename, data, mode=wire_mode, branch=branch)
        # Files dataset: branchless raw file store; replace clears it first.
        if mode == "replace":
            fs.clear()
        return fs.write(filename, data)

    def write_dataframes(
        self,
        dfs: Iterable[Any],
        *,
        format: str = "parquet",
        mode: str = "replace",
        prefix: str = "part",
    ) -> List[Dict[str, Any]]:
        """Write an iterable/iterator of DataFrame chunks as separate part files
        (``part-00000.parquet`` …). ``mode="replace"`` clears the dataset once
        up front, then every chunk is appended — the counterpart of
        :meth:`TransformInput.iter_dataframes` for streaming large outputs.
        """
        if mode not in ("replace", "append"):
            raise ValueError(f"Unsupported mode '{mode}' (use 'replace' or 'append')")
        fs = self.filesystem()
        branch = _catalog_branch()
        iceberg = _is_iceberg(self._client, self.dataset_id)
        # Files dataset: clear once up front. Iceberg: the first chunk of a
        # replace is a SNAPSHOT (overwrites the branch) and the rest APPEND.
        if mode == "replace" and not iceberg:
            fs.clear()
        results: List[Dict[str, Any]] = []
        for i, df in enumerate(dfs):
            data, ext = _serialize_df(df, format)
            name = f"{prefix}-{i:05d}.{ext}"
            if iceberg:
                wire_mode = "SNAPSHOT" if (mode == "replace" and i == 0) else "APPEND"
                results.append(fs.write(name, data, mode=wire_mode, branch=branch))
            else:
                results.append(fs.write(name, data))
        return results

    def filesystem(self) -> FileSystem:
        return FileSystem(self._client, self.dataset_id)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def _catalog_models() -> Dict[str, Dict[str, Any]]:
    """The models the build engine resolved for this run, keyed by alias
    (`CATALOG_MODELS`): ``{alias: {model_id, path, parameters, version}}`` where
    ``path`` is the model's directory **in this checkout**. Empty outside a
    build."""
    import json

    raw = os.environ.get("CATALOG_MODELS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


def _resolve_model(client: Any, ref: str) -> Dict[str, Any]:
    """Resolve ``"<project_alias>.<model_alias>"`` (or a bare alias / id) to the
    model row, using the catalog's ``/models`` endpoint."""
    alias = ref.split(".", 1)[1] if "." in ref else ref
    project_alias = ref.split(".", 1)[0] if "." in ref else None

    models = _catalog_get(client, "/models")
    if project_alias:
        project = next((p for p in client.projects.list() if p.get("alias") == project_alias), None)
        if project is None:
            raise GwenlakeException(f"No project with alias '{project_alias}' (in ref '{ref}')")
        models = [m for m in models if m.get("project_id") == project["id"]]
    match = next((m for m in models if m.get("alias") == alias or m.get("id") == ref), None)
    if match is None:
        raise GwenlakeException(
            f"No model '{ref}' in the catalog. Note that the catalog's /models "
            "endpoints are only reachable from a build (the client's base URL "
            "must be the api-catalog service): on the public gateway /models is "
            "the inference model list."
        )
    return match


def _catalog_get(client: Any, url: str) -> List[Dict[str, Any]]:
    from gwenlake.client import RequestOptions

    response = client._client.send(RequestOptions(method="GET", url=url))
    response.raise_for_status()
    return response.json().get("data", [])


class TransformModel:
    """A model bound to a transform — its artifacts on disk, plus its card.

    Inside a build the engine has already checked out the repository and told
    us where the model lives (`CATALOG_MODELS`), so ``path`` is a real local
    directory and **no API call is needed** — which is what makes this usable
    today: the catalog's ``/models`` endpoints are not routed through the
    public gateway (that path serves the inference model list), so ``info()``
    and ``update()`` only work when the client points at api-catalog, as it
    does inside a build.
    """

    def __init__(self, client: Any, ref: str):
        self._client = client
        self.ref = ref
        self._info: Optional[Dict[str, Any]] = None
        self._env = _catalog_models().get(ref.split(".", 1)[-1]) or {}

    # -- identity / card ---------------------------------------------------

    @property
    def id(self) -> str:
        if self._env.get("model_id"):
            return self._env["model_id"]
        return self.info()["id"]

    @property
    def path(self) -> str:
        """Local directory holding the model's files."""
        if self._env.get("path"):
            return self._env["path"]
        return self.info().get("path") or "."

    @property
    def parameters(self) -> Dict[str, Any]:
        if self._env:
            return dict(self._env.get("parameters") or {})
        return dict(self.info().get("parameters") or {})

    @property
    def version(self) -> Optional[str]:
        if self._env:
            return self._env.get("version")
        return self.info().get("version")

    def info(self) -> Dict[str, Any]:
        """The model row from the catalog (cached)."""
        if self._info is None:
            self._info = _resolve_model(self._client, self.ref)
        return self._info

    # -- writing back ------------------------------------------------------

    def update(self, **fields: Any) -> Dict[str, Any]:
        """PATCH the model card (``metrics=...``, ``version=...``, ``parameters=...``).

        The artifacts themselves are committed by the build engine — a training
        run only has to write them under :attr:`path`.
        """
        from gwenlake.client import RequestOptions

        response = self._client._client.send(RequestOptions(
            method="PATCH", url=f"/models/{self.id}",
            headers={"Content-Type": "application/json"}, json_data=fields,
        ))
        response.raise_for_status()
        self._info = response.json()
        return self._info

    def file(self, *parts: str) -> str:
        """``os.path.join(model.path, *parts)`` — the usual way to address an
        artifact (``model.file("model.pkl")``)."""
        return os.path.join(self.path, *parts)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def _split_bindings(
    bindings: Dict[str, _DatasetRef],
) -> Tuple[Dict[str, Input], Dict[str, Output], Dict[str, Model]]:
    inputs = {k: v for k, v in bindings.items() if isinstance(v, Input)}
    outputs = {k: v for k, v in bindings.items() if isinstance(v, Output)}
    models = {k: v for k, v in bindings.items() if isinstance(v, Model)}
    unknown = {k: v for k, v in bindings.items() if not isinstance(v, _DatasetRef)}
    if unknown:
        raise TypeError(f"transform bindings must be Input/Model/Output, got: {list(unknown)}")
    return inputs, outputs, models


def transform_df(**bindings: _DatasetRef) -> Callable:
    """Decorate a function that takes ``Input`` DataFrames (by keyword name) and
    returns a single DataFrame, written to the (single) ``Output``.

    The decorated function is called as ``fn(client)`` and runs eagerly: it
    reads every input, calls the body, and writes the returned DataFrame.
    """
    inputs, outputs, models = _split_bindings(bindings)
    if len(outputs) != 1:
        raise TypeError(f"transform_df expects exactly one Output, got {len(outputs)}")

    def decorator(fn: Callable) -> Callable:
        params = inspect.signature(fn).parameters

        @functools.wraps(fn)
        def wrapper(client: Any) -> Any:
            call_kwargs: Dict[str, Any] = {}
            for name in params:
                if name in inputs:
                    call_kwargs[name] = TransformInput(client, inputs[name].ref).dataframe()
                elif name in models:
                    call_kwargs[name] = TransformModel(client, models[name].ref)
                elif name in outputs:
                    # Tolerated for parity with the user's snippet; the return
                    # value is what actually gets written.
                    call_kwargs[name] = TransformOutput(client, outputs[name].ref)
            result = fn(**call_kwargs)
            if result is not None:
                out = next(iter(outputs.values()))
                TransformOutput(client, out.ref).write_dataframe(result)
            return result

        wrapper.inputs = inputs
        wrapper.outputs = outputs
        wrapper.models = models
        return wrapper

    return decorator


def transform(**bindings: _DatasetRef) -> Callable:
    """Decorate a function that takes ``TransformInput`` / ``TransformOutput``
    objects (by keyword name). The body is responsible for reading
    (``.dataframe()`` / ``.filesystem()``) and writing (``.write_dataframe()`` /
    ``.filesystem().write()``) explicitly.

    The decorated function is called as ``fn(client)`` and runs eagerly.
    """
    inputs, outputs, models = _split_bindings(bindings)

    def decorator(fn: Callable) -> Callable:
        params = inspect.signature(fn).parameters

        @functools.wraps(fn)
        def wrapper(client: Any) -> Any:
            call_kwargs: Dict[str, Any] = {}
            for name in params:
                if name in inputs:
                    call_kwargs[name] = TransformInput(client, inputs[name].ref)
                elif name in models:
                    call_kwargs[name] = TransformModel(client, models[name].ref)
                elif name in outputs:
                    call_kwargs[name] = TransformOutput(client, outputs[name].ref)
            return fn(**call_kwargs)

        wrapper.inputs = inputs
        wrapper.outputs = outputs
        wrapper.models = models
        return wrapper

    return decorator


def train(**bindings: _DatasetRef) -> Callable:
    """Decorate a function that **trains a model**: its ``Output`` is a model,
    not a dataset.

        @train(
            training_set=Input("crm.churn-training"),
            output=Output("crm.churn"),
        )
        def fit(training_set, output):
            clf = ...                                   # training_set is a DataFrame
            joblib.dump(clf, output.file("model.pkl"))   # write under the model's dir
            return {"auc": 0.91}                         # -> stored as the model's metrics

    ``Input`` bindings arrive as ``pandas.DataFrame`` (as in ``transform_df``);
    ``Model`` bindings and the ``Output`` arrive as :class:`TransformModel`, so
    ``output.path`` is the model's directory **in this checkout** — the build
    engine commits whatever the function writes there and pins that commit as
    the model's version. A returned dict is stored as the model's ``metrics``.

    A ``Model`` binding alongside the ``Output`` expresses fine-tuning: the
    lineage then reads model -> train -> model.
    """
    inputs, outputs, models = _split_bindings(bindings)
    if len(outputs) != 1:
        raise TypeError(f"train expects exactly one Output (the model), got {len(outputs)}")

    def decorator(fn: Callable) -> Callable:
        params = inspect.signature(fn).parameters

        @functools.wraps(fn)
        def wrapper(client: Any) -> Any:
            call_kwargs: Dict[str, Any] = {}
            for name in params:
                if name in inputs:
                    call_kwargs[name] = TransformInput(client, inputs[name].ref).dataframe()
                elif name in models:
                    call_kwargs[name] = TransformModel(client, models[name].ref)
                elif name in outputs:
                    call_kwargs[name] = TransformModel(client, outputs[name].ref)
            result = fn(**call_kwargs)
            if isinstance(result, dict):
                TransformModel(client, next(iter(outputs.values())).ref).update(metrics=result)
            return result

        wrapper.inputs = inputs
        wrapper.outputs = outputs
        wrapper.models = models
        return wrapper

    return decorator
