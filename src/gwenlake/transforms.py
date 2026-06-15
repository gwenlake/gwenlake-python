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

Two decorators are provided:

* ``transform_df`` — the decorated function receives each ``Input`` as a
  ``pandas.DataFrame`` (matched by keyword name) and **returns** a single
  DataFrame which is written to the (single) ``Output``.
* ``transform`` — the lower-level form: the function receives ``TransformInput``
  and ``TransformOutput`` objects (matched by keyword name). Call
  ``.dataframe()`` to read, ``.write_dataframe(df)`` to write, and
  ``.filesystem()`` for raw file access (images, PDFs, anything non-tabular).

Datasets are addressed as ``"<project_alias>.<dataset_alias>"`` — the same
handle DuckDB uses in ``FROM '<project>.<dataset>'``. A bare string with no dot
is treated as a dataset alias (searched across datasets) or, failing that, as a
dataset id.

``pandas`` (and ``pyarrow`` for parquet) are optional dependencies, imported
lazily so the base SDK stays light. Install with ``pip install gwenlake[transforms]``.
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
    """References the output dataset a transform writes to."""


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
            "pandas is required for transforms; install with: pip install gwenlake[transforms]"
        ) from exc
    return pd


def _sql_table(client: Any, ref: str) -> str:
    """The '<project>.<dataset>' table handle DuckDB uses in FROM, from a ref."""
    return ref if "." in ref else _ref_to_sql_table(client, ref)


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

    def write(self, filepath: str, data: bytes) -> Dict[str, Any]:
        """Upload raw bytes to ``filepath`` within the dataset."""
        path, filename = _split_path(filepath)
        return self._client.files.upload(self._dataset_id, data, path=path, filename=filename)

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
        if mode == "replace":
            fs.clear()
        results: List[Dict[str, Any]] = []
        for i, df in enumerate(dfs):
            data, ext = _serialize_df(df, format)
            results.append(fs.write(f"{prefix}-{i:05d}.{ext}", data))
        return results

    def filesystem(self) -> FileSystem:
        return FileSystem(self._client, self.dataset_id)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def _split_bindings(bindings: Dict[str, _DatasetRef]) -> Tuple[Dict[str, Input], Dict[str, Output]]:
    inputs = {k: v for k, v in bindings.items() if isinstance(v, Input)}
    outputs = {k: v for k, v in bindings.items() if isinstance(v, Output)}
    unknown = {k: v for k, v in bindings.items() if not isinstance(v, _DatasetRef)}
    if unknown:
        raise TypeError(f"transform bindings must be Input/Output, got: {list(unknown)}")
    return inputs, outputs


def transform_df(**bindings: _DatasetRef) -> Callable:
    """Decorate a function that takes ``Input`` DataFrames (by keyword name) and
    returns a single DataFrame, written to the (single) ``Output``.

    The decorated function is called as ``fn(client)`` and runs eagerly: it
    reads every input, calls the body, and writes the returned DataFrame.
    """
    inputs, outputs = _split_bindings(bindings)
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
        return wrapper

    return decorator


def transform(**bindings: _DatasetRef) -> Callable:
    """Decorate a function that takes ``TransformInput`` / ``TransformOutput``
    objects (by keyword name). The body is responsible for reading
    (``.dataframe()`` / ``.filesystem()``) and writing (``.write_dataframe()`` /
    ``.filesystem().write()``) explicitly.

    The decorated function is called as ``fn(client)`` and runs eagerly.
    """
    inputs, outputs = _split_bindings(bindings)

    def decorator(fn: Callable) -> Callable:
        params = inspect.signature(fn).parameters

        @functools.wraps(fn)
        def wrapper(client: Any) -> Any:
            call_kwargs: Dict[str, Any] = {}
            for name in params:
                if name in inputs:
                    call_kwargs[name] = TransformInput(client, inputs[name].ref)
                elif name in outputs:
                    call_kwargs[name] = TransformOutput(client, outputs[name].ref)
            return fn(**call_kwargs)

        wrapper.inputs = inputs
        wrapper.outputs = outputs
        return wrapper

    return decorator
