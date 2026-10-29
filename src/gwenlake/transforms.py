"""Transforms over the Gwenlake catalog.

Decorators that read, compute and write datasets on top of the Gwenlake
client:

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
  ``pandas.DataFrame`` (matched by keyword name) and **returns** the DataFrame
  written to its ``Output`` — or, with several ``Output``s, a dict keyed by
  their keyword names.
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

A fourth, ``Connection("<project>.<connection>")``, binds a **connection** —
an SMB share, a bucket, a SharePoint library — the transform reads *itself*,
instead of having a sync copy it first. It arrives as a ``TransformConnection``
whose ``.filesystem()`` walks the source (read-only) through the catalog, so
the connection's credentials never reach the code::

    @transform(
        share=Connection("ops.drop-folder"),
        out=Output("ops.collected"),
    )
    def collect(share, out):
        fs_in, fs_out = share.filesystem(), out.filesystem()
        for f in fs_in.ls(glob="**/*.pdf"):
            with fs_in.open(f["path"], "rb") as src, fs_out.open(f["path"], "wb") as dst:
                shutil.copyfileobj(src, dst)

``@incremental`` (stacked above ``@transform`` or ``@transform_df``) is for a
transform that keeps its own memory in an
Output — the log of what it has already processed — and reads it back on the
next run, instead of starting over::

    @incremental(semantic_version=1)
    @transform(
        share=Connection("ops.drop-folder"),
        out=Output("ops.pages"),
        log=Output("ops.processed"),
    )
    def ingest(share, out, log):
        done = set(log.dataframe("previous", schema=["path"])["path"])
        new = [f for f in share.filesystem().ls(glob="**/*.pdf") if f["path"] not in done]
        if not new:
            return
        out.write_dataframe(parse(new))                                  # appended
        log.write_dataframe(pd.DataFrame({"path": [f["path"] for f in new]}))

Under it an Output answers ``dataframe("previous", schema)`` — its content at
the end of the last successful run, an empty frame of ``schema`` while there is
none — and ``dataframe("current")``; and its writes **add** to it
(``set_mode("modify")``, the default) unless ``set_mode("replace")`` asks for a
snapshot. Bumping ``semantic_version`` makes the next build start over. An
Output can never be an Input of the same transform (that is a cycle in the
lineage); reading it as ``"previous"`` is how it is relied on without one.
Inputs have no ``"added"`` mode here: the catalog keeps no transaction log, so
every input is read whole on every run — a *snapshot input* — and remembering
what was done is the Output's job.

Datasets are addressed as ``"<project_alias>.<dataset_alias>"`` — the same
handle DuckDB uses in ``FROM '<project>.<dataset>'``. A bare string with no dot
is treated as a dataset alias (searched across datasets) or, failing that, as a
dataset id.

Reads move over Arrow rather than JSON, and an ``Input`` can restrict what it
pulls back — decisive on wide tables, where a transform typically wants a
handful of a few hundred columns::

    @transform_df(
        taxes=Input("gda.tax-ciblage", columns=["Id", "Asset__r"], chunk_size=5_000),
        out=Output("gda.ciblage-train"),
    )

``pandas`` and ``pyarrow`` are included in the base install.
"""

import functools
import inspect
import io
import contextlib
import os
import re
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

from gwenlake.exceptions import GwenlakeException


# Rows per page when reading/writing a dataset in chunks (LIMIT/OFFSET).
DEFAULT_CHUNK_SIZE = 50_000

# A full scan of a large dataset is not an ordinary request: the engine has to
# read every parquet file behind it before the first byte comes back, which can
# take minutes. The client's 60s default is a timeout on *that*, so reads carry
# their own — otherwise a big input fails with `httpx.ReadTimeout` regardless of
# how well the query itself is doing.
DEFAULT_READ_TIMEOUT = 600.0


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
    """References an input dataset for a transform.

    ``columns`` restricts the read to the named top-level columns — the single
    most effective way to cut the cost of a wide dataset, since a transform that
    uses ten of two hundred columns otherwise pays to move all two hundred.
    ``chunk_size`` and ``order_by`` steer the LIMIT/OFFSET paging.
    """

    def __init__(
        self,
        ref: str,
        *,
        columns: Optional[Iterable[str]] = None,
        chunk_size: Optional[int] = DEFAULT_CHUNK_SIZE,
        order_by: Optional[str] = None,
    ):
        super().__init__(ref)
        self.columns = list(columns) if columns is not None else None
        self.chunk_size = chunk_size
        self.order_by = order_by

    def read_options(self) -> Dict[str, Any]:
        return {"columns": self.columns, "chunk_size": self.chunk_size, "order_by": self.order_by}


class Output(_DatasetRef):
    """References what a transform produces: the output dataset of a
    ``transform``/``transform_df``, or the **model** of a ``train``."""


class Model(_DatasetRef):
    """References a model the transform loads, e.g. ``Model("crm.churn")``.

    Conventionally bound to the ``model=`` keyword. The decorated function
    receives a :class:`TransformModel` — use ``model.path`` to read the
    artifacts, which live in the same repository as this code.
    """


class Connection(_DatasetRef):
    """References a connection the transform reads, e.g.
    ``Connection("ops.drop-folder")`` — a ``"<project>.<connection slug>"`` ref
    or a ``res.connection.*`` id.

    The decorated function receives a :class:`TransformConnection`; its
    ``.filesystem()`` lists and opens the files the connection holds, through
    the catalog and as the build's own identity. In a catalog build the engine
    exports ``CATALOG_CONNECTIONS`` (slug → id), so no lookup is needed.
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


def _catalog_connections() -> Dict[str, str]:
    """``CATALOG_CONNECTIONS`` as the build engine exports it: ``{slug: id}``
    for every connection the transform resource declares as an input. Empty
    outside a build."""
    import json

    raw = os.environ.get("CATALOG_CONNECTIONS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


def _resolve_connection_id(client: Any, ref: str) -> str:
    """Resolve ``"<project>.<slug>"`` (or a bare slug / id) to a connection id:
    the build's ``CATALOG_CONNECTIONS`` first, else the catalog's listing."""
    if ref.startswith("res.connection."):
        return ref
    slug = ref.split(".", 1)[1] if "." in ref else ref
    exported = _catalog_connections()
    if slug in exported:
        return exported[slug]
    rows = client.connections.list()
    if "." in ref:
        project_slug = ref.split(".", 1)[0]
        project = next(
            (p for p in client.projects.list() if (p.get("slug") or p.get("alias")) == project_slug), None,
        )
        if project is None:
            raise GwenlakeException(f"No project '{project_slug}' (in ref '{ref}')")
        rows = [c for c in rows if c.get("project_id") == project["id"]]
    match = next((c for c in rows if (c.get("slug") or c.get("alias")) == slug or c.get("id") == ref), None)
    if match is None:
        raise GwenlakeException(f"No connection '{ref}' in the catalog")
    return match["id"]


def _glob_regex(pattern: str) -> "re.Pattern[str]":
    """A glob as a regex over a relative path, with path semantics: ``*`` and
    ``?`` stay within one directory, ``**`` crosses into subdirectories (the
    rule the catalog's own file matching follows)."""
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile(r"\A" + "".join(out) + r"\Z")


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
    syntax `/sql` understands. A files input has one version and answers it
    whatever the suffix, server-side."""
    handle = ref if "." in ref else _ref_to_sql_table(client, ref)
    if "@" in handle:
        # Already a snapshot handle (`project.dataset[:branch]@…`), built by
        # `IncrementalTransformInput` on top of this function: as-is.
        return handle
    branch = _catalog_branch()
    return f"{handle}:{branch}" if branch else handle


def _require_pyarrow_parquet():
    """`pyarrow.parquet`, or a message naming what to install."""
    try:
        import pyarrow.parquet as pq
    except ImportError as e:                                  # pragma: no cover
        raise GwenlakeException(
            "writing Parquet needs pyarrow (pip install pyarrow)") from e
    return pq


def _require_pyarrow():
    try:
        import pyarrow as pa
    except ImportError as exc:  # pragma: no cover
        raise GwenlakeException(
            "pyarrow is required for transforms; install with: pip install gwenlake"
        ) from exc
    return pa


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _select_clause(columns: Optional[Iterable[str]]) -> str:
    """The projection to put after SELECT — every column, or just the named ones."""
    cols = list(columns) if columns is not None else None
    if not cols:
        return "*"
    return ", ".join(_quote_ident(c) for c in cols)


def _run_arrow(client: Any, statement: str) -> Any:
    """Run a SQL statement and return its result as a ``pyarrow.Table``.

    Arrow, not JSON: these payloads are dominated by wide, deeply nested rows,
    and JSON re-encodes every field name on every row. On a 232-column Salesforce
    export that is a ~27x blow-up over the columnar form (112 MB of parquet
    becomes ~3 GB of JSON), which is what turns an ordinary read into a timeout.
    """
    pa = _require_pyarrow()
    content = client.statements.create(
        statement=statement, format="pyarrow", timeout=DEFAULT_READ_TIMEOUT
    )
    if not content:
        return pa.table({})
    with pa.ipc.open_file(pa.BufferReader(content)) as reader:
        return reader.read_all()


def _iter_arrow_pages(
    client: Any,
    table: str,
    chunk_size: int,
    columns: Optional[Iterable[str]] = None,
    order_by: Optional[str] = None,
) -> Iterator[Any]:
    """Yield successive pages as ``pyarrow.Table`` via ``LIMIT/OFFSET`` until
    exhausted.

    Without an ``order_by`` the page boundaries rely on the engine's scan order,
    which DuckDB keeps stable for a static dataset; pass ``order_by`` (e.g. a
    primary key) for a guaranteed-deterministic split.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    projection = _select_clause(columns)
    order = f" ORDER BY {order_by}" if order_by else ""
    offset = 0
    while True:
        page = _run_arrow(
            client,
            f"SELECT {projection} FROM '{table}'{order} LIMIT {chunk_size} OFFSET {offset}",
        )
        if page.num_rows == 0:
            break
        yield page
        if page.num_rows < chunk_size:
            break
        offset += chunk_size


def _iter_dataframes(
    client: Any,
    ref: str,
    chunk_size: int,
    columns: Optional[Iterable[str]] = None,
    order_by: Optional[str] = None,
) -> Iterator[Any]:
    """Yield the dataset as successive ``pandas.DataFrame`` chunks."""
    _require_pandas()
    table = _sql_table(client, ref)
    for page in _iter_arrow_pages(client, table, chunk_size, columns, order_by):
        yield page.to_pandas()


def _read_dataframe(
    client: Any,
    ref: str,
    *,
    columns: Optional[Iterable[str]] = None,
    chunk_size: Optional[int] = None,
    order_by: Optional[str] = None,
):
    """Read a dataset into a single ``pandas.DataFrame``.

    With ``chunk_size=None`` it issues one ``SELECT``. Pass a ``chunk_size`` to
    page through with ``LIMIT/OFFSET`` and concatenate — same result, but bounded
    request/response sizes for very large datasets. ``columns`` restricts the
    projection.
    """
    pd = _require_pandas()
    if chunk_size is None:
        table = _sql_table(client, ref)
        return _run_arrow(
            client, f"SELECT {_select_clause(columns)} FROM '{table}'"
        ).to_pandas()
    chunks = list(_iter_dataframes(client, ref, chunk_size, columns, order_by))
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def _table_has_rows(client: Any, ref: str) -> bool:
    import httpx

    try:
        table = _run_arrow(client, f"SELECT 1 AS present FROM '{_sql_table(client, ref)}' LIMIT 1")
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 400 and "has no table yet" in error.response.text:
            return False
        raise
    return table.num_rows > 0


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
    """Raw S3-backed file access for a dataset.

    In a branch build (``CATALOG_BRANCH`` set) every call carries the build's
    branch. On an Iceberg dataset that is the branch's view; a files dataset
    has one version, which its reads answer whatever the branch — and which a
    branch build never writes, since the catalog refuses such a build before
    it starts.
    """

    def __init__(self, client: Any, dataset_id: str):
        self._client = client
        self._dataset_id = dataset_id

    def _list(self, path: Optional[str]) -> List[Dict[str, Any]]:
        return self._client.files.list(self._dataset_id, path=path, branch=_catalog_branch())

    def ls(self, path: Optional[str] = None, *, glob: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files in the dataset (optionally under ``path``).

        Without ``glob``, the entries of that one directory, as the catalog
        lists them. With ``glob``, the **files** matching it — ``*`` within a
        directory, ``**`` across, so ``ls(glob="**/*.pdf")`` walks the whole
        dataset — each with a ``path`` relative to the dataset's root, the same
        value :meth:`read`/:meth:`open` take.
        """
        entries = self._list(path)
        if glob is None:
            return entries
        return list(self._walk(path, entries, _glob_regex(glob), recursive="**" in glob))

    def _walk(self, path, entries, selector, *, recursive):
        for entry in entries or []:
            filepath = _entry_path(entry)
            if not filepath or filepath.rstrip("/") == (path or "").rstrip("/"):
                continue
            if _is_directory(entry):
                if recursive:
                    sub = filepath.rstrip("/")
                    yield from self._walk(sub, self._list(sub), selector, recursive=True)
                continue
            if selector.search(filepath):
                yield {**entry, "path": filepath, "filename": filepath.rsplit("/", 1)[-1]}

    # Alias
    files = ls

    def read(self, filepath: str) -> bytes:
        """Download a file's raw bytes."""
        return self._client.files.download(self._dataset_id, filepath, branch=_catalog_branch())

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
        return self._client.files.delete(self._dataset_id, filepath, branch=_catalog_branch())

    def clear(self, path: Optional[str] = None) -> int:
        """Delete every file in the dataset (recursively, descending into any
        sub-folders); returns the number removed. The snapshot (replace) write
        semantics."""
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

    def __init__(
        self,
        client: Any,
        ref: str,
        *,
        columns: Optional[Iterable[str]] = None,
        chunk_size: Optional[int] = DEFAULT_CHUNK_SIZE,
        order_by: Optional[str] = None,
    ):
        self._client = client
        self.ref = ref
        self._dataset_id: Optional[str] = None
        #: Compté à la demande, puis gardé : la taille d'un jeu ne bouge pas
        #: pendant un entraînement, et `epochs` la redemanderait à chaque époque.
        self._rows: Optional[int] = None
        # Defaults from the binding (`Input(..., columns=[...])`), overridable
        # per call.
        self.columns = list(columns) if columns is not None else None
        self.chunk_size = chunk_size
        self.order_by = order_by

    @property
    def dataset_id(self) -> str:
        if self._dataset_id is None:
            self._dataset_id = _resolve_dataset_id(self._client, self.ref)
        return self._dataset_id

    def dataframe(
        self,
        *,
        columns: Optional[Iterable[str]] = None,
        chunk_size: Optional[int] = None,
        order_by: Optional[str] = None,
    ):
        """Read the whole dataset into a ``pandas.DataFrame``.

        With ``chunk_size`` set, pages through with ``LIMIT/OFFSET`` and
        concatenates (bounded request sizes); with ``chunk_size=None``, one
        ``SELECT``. ``columns`` restricts the projection. Unset arguments fall
        back to whatever the ``Input`` binding declared.
        """
        return _read_dataframe(
            self._client,
            self.ref,
            columns=self.columns if columns is None else columns,
            chunk_size=self.chunk_size if chunk_size is None else chunk_size,
            order_by=self.order_by if order_by is None else order_by,
        )

    def iter_dataframes(
        self,
        *,
        columns: Optional[Iterable[str]] = None,
        chunk_size: Optional[int] = None,
        order_by: Optional[str] = None,
    ) -> Iterator[Any]:
        """Iterate over the dataset as ``pandas.DataFrame`` chunks of ``chunk_size``
        rows — for datasets too large to hold in memory at once."""
        return _iter_dataframes(
            self._client,
            self.ref,
            chunk_size or self.chunk_size or DEFAULT_CHUNK_SIZE,
            self.columns if columns is None else columns,
            self.order_by if order_by is None else order_by,
        )

    def batches(
        self,
        size: int = 32,
        *,
        columns: Optional[Iterable[str]] = None,
        chunk_size: Optional[int] = None,
        order_by: Optional[str] = None,
    ) -> Callable[[], Iterator[Any]]:
        """Training batches of ``size`` rows, ready for :meth:`Run.steps`::

            for step, batch in run.steps(train.batches(32)):

        Returns a CALLABLE, not a generator, and that is the point: an epoch
        ends when the source runs out, and an exhausted iterator cannot be
        walked again. `run.steps` calls this once per epoch to get a fresh
        pass, which a generator handed in directly could never give.

        Two sizes, doing different jobs: ``chunk_size`` is how many rows come
        back per request -- large, because round trips dominate -- and ``size``
        is how many rows the model sees at once. Slicing the pages locally is
        what lets those two be chosen independently.
        """
        page_rows = chunk_size or self.chunk_size or DEFAULT_CHUNK_SIZE

        def pass_over() -> Iterator[Any]:
            for page in self.iter_dataframes(
                columns=columns, chunk_size=page_rows, order_by=order_by,
            ):
                for start in range(0, len(page), size):
                    batch = page.iloc[start:start + size]
                    if len(batch):
                        yield batch

        return pass_over

    @property
    def rows(self) -> int:
        """How many rows the dataset holds.

        Counted server-side, so it costs one query and no transfer -- which is
        what makes it usable to turn "two epochs" into a step budget without
        reading the data first.
        """
        if self._rows is None:
            # Même forme que la lecture paginée : la ref EST le nom de table.
            table = _run_arrow(
                self._client, f"SELECT COUNT(*) AS n FROM '{self.ref}'")
            self._rows = int(table.column("n")[0].as_py()) if table.num_rows else 0
        return self._rows

    def __len__(self) -> int:
        return self.rows

    def to_parquet(
        self,
        destination: Any,
        *,
        columns: Optional[Iterable[str]] = None,
        chunk_size: Optional[int] = None,
        reuse: bool = True,
        attempts: int = 3,
    ) -> int:
        """Write the dataset to a local Parquet file. Returns the row count.

        For the training libraries that read FILES rather than a stream --
        anything that shuffles by permuting row groups, which a paged source
        cannot offer. Streaming stays the better path when the loop can take
        it (see :meth:`batches`); this is for when it cannot.

        Written to a temporary name and renamed at the end, so **a file that
        exists is a file that is complete**. Reading a million rows takes
        dozens of requests, and one dropping mid-way otherwise leaves a
        perfectly readable Parquet holding a fraction of the data -- which the
        next attempt believes is the whole dataset, and trains on it without
        anything saying so.

        ``reuse`` keeps an existing complete file: that is what makes a
        resumed run skip the download instead of paying for it again.

        Retried as a WHOLE rather than resumed: reading a million rows takes
        dozens of requests, and one dropping in the middle -- a
        `RemoteProtocolError`, a gateway recycling a connection -- is common
        enough to lose a staging over. A paged read has no cursor to restart
        from, and re-reading costs far less than a training that dies at
        minute six.
        """
        from pathlib import Path

        pq = _require_pyarrow_parquet()

        target = Path(destination)
        if reuse and target.exists():
            return int(pq.ParquetFile(target).metadata.num_rows)

        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".partial")
        last: Optional[BaseException] = None
        for attempt in range(1, max(1, attempts) + 1):
            try:
                return self._write_parquet(partial, target, columns, chunk_size)
            except (GwenlakeException, KeyboardInterrupt):
                raise
            except BaseException as e:                        # noqa: BLE001
                last = e
                print(f"gwenlake: staging {target.name}: attempt {attempt}/"
                      f"{attempts} failed ({type(e).__name__}: {e})", flush=True)
        raise GwenlakeException(
            f"could not stage '{self.ref}' after {attempts} attempts") from last

    def _write_parquet(self, partial, target, columns, chunk_size) -> int:
        """One attempt: write every page, then rename into place."""
        pq = _require_pyarrow_parquet()
        pa = _require_pyarrow()
        writer, rows = None, 0
        try:
            for page in self.iter_dataframes(columns=columns, chunk_size=chunk_size):
                table = pa.Table.from_pandas(page, preserve_index=False)
                if writer is None:
                    # One row group per page -- that is the unit a shuffle
                    # permutes, so there had better be several of them.
                    writer = pq.ParquetWriter(partial, table.schema)
                writer.write_table(table)
                rows += len(page)
            if writer is None:
                raise GwenlakeException(f"'{self.ref}' returned no row at all")
            writer.close()
            writer = None
            partial.replace(target)
            return rows
        except BaseException:
            if writer is not None:
                with contextlib.suppress(Exception):
                    writer.close()
            partial.unlink(missing_ok=True)
            raise

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
        a snapshot write; ``mode="append"`` just adds the file
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
# Incremental transforms (``@incremental``)
# ---------------------------------------------------------------------------

#: How an incremental Output takes a write: ``modify`` adds to what is there
#: (the default under ``@incremental``), ``replace`` starts the dataset over.
INCREMENTAL_WRITE_MODES = ("modify", "replace")

_INPUT_MODES_REFUSED = ("added", "previous")


def _run_id() -> str:
    """What makes this run's part files unique in the output: the catalog's
    build id when the engine exports one (``CATALOG_BUILD_ID``), a UTC
    timestamp for a local run. Only filename-safe characters are kept."""
    build = os.environ.get("CATALOG_BUILD_ID", "").strip()
    if not build:
        from datetime import datetime, timezone

        build = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return re.sub(r"[^A-Za-z0-9_-]+", "-", build)


def _catalog_incremental() -> Dict[str, Dict[str, Any]]:
    """``CATALOG_INCREMENTAL`` as the build engine exports it: per output
    dataset id, the ``semantic_version`` the last successful incremental build
    wrote it with. Empty outside a build, and for an output no incremental
    build has written yet — in both cases nothing starts over."""
    import json

    raw = os.environ.get("CATALOG_INCREMENTAL", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


def _empty_dataframe(schema: Any):
    """An empty ``pandas.DataFrame`` shaped by ``schema``: a list of column
    names, a ``{name: dtype}`` mapping, a ``pyarrow.Schema``, or a DataFrame
    whose columns to copy. ``None`` gives a frame with no columns at all."""
    pd = _require_pandas()
    if schema is None:
        return pd.DataFrame()
    if hasattr(schema, "iloc"):          # a DataFrame
        return schema.iloc[0:0].copy()
    if hasattr(schema, "empty_table"):   # a pyarrow.Schema
        return schema.empty_table().to_pandas()
    if isinstance(schema, dict):
        return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in schema.items()})
    return pd.DataFrame(columns=list(schema))


def _catalog_input_snapshots() -> Dict[str, Dict[str, Any]]:
    """``CATALOG_INPUT_SNAPSHOTS`` as the build engine exports it for an
    incremental run: per input slug, ``{id, from, to}`` — the Iceberg snapshot
    the last successful build read up to (``from``, null on a first run or
    when the run starts over) and the head pinned before this run (``to``).
    Only Iceberg inputs holding a table appear. Empty outside a build."""
    import json

    raw = os.environ.get("CATALOG_INPUT_SNAPSHOTS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


_INPUT_MODES = ("current", "added", "previous")


class IncrementalTransformInput(TransformInput):
    """An input under ``@incremental``: :class:`TransformInput` plus a
    ``mode`` argument.

    ``"current"`` is the whole dataset. ``"added"`` and ``"previous"`` exist for an **Iceberg** input inside
    a build: the table's snapshots are its transaction log, the engine pins
    where it stood before the run (``CATALOG_INPUT_SNAPSHOTS``), and the read
    is ``project.dataset@from..to`` — the rows appended since the last
    successful run, up to that pinned head, never "now" — or ``@from``, the
    table as the last run saw it. On a first run, or when the run starts
    over, ``added`` is everything and ``previous`` is empty.

    Anything else — a files dataset, a mediaset, a run outside a build — is
    refused for those two modes rather than quietly answered with everything:
    a body believing it sees only the new rows would process the whole
    dataset again on every run. For those the memory belongs in an Output,
    read back as ``output.dataframe("previous")``. The catalog also refuses
    ``added`` when the table was rewritten in between (an overwrite, a delete,
    an upsert): there is no delta then, and the error says to read the table
    whole or bump ``semantic_version``.
    """

    def _snapshots(self) -> Optional[Dict[str, Any]]:
        exported = _catalog_input_snapshots()
        slug = self.ref.split(".", 1)[-1]
        if slug in exported:
            return exported[slug]
        return next((v for v in exported.values() if v.get("id") == self.ref), None)

    def _table(self, mode: str) -> str:
        """The table handle for ``mode``: the plain one for ``current``, the
        ``@`` form for ``added`` / ``previous``."""
        if mode == "current":
            return _sql_table(self._client, self.ref)
        if mode not in _INPUT_MODES:
            raise GwenlakeException(f"unknown input mode {mode!r} (use 'current', 'added' or 'previous')")
        span = self._snapshots()
        if span is None:
            raise GwenlakeException(
                f"{self.ref}: input mode {mode!r} needs an Iceberg input inside a build — the "
                "catalog keeps no transaction log of a files dataset or a connection, so those "
                "are always read whole (a snapshot input). Keep the keys you have "
                "processed in an Output and read them back with output.dataframe('previous')."
            )
        handle = _sql_table(self._client, self.ref)
        since, until = span.get("from"), span.get("to")
        if mode == "added":
            return f"{handle}@{since}..{until}" if since is not None else f"{handle}@{until}"
        # previous: the table as the last run saw it — nothing, before any run.
        return f"{handle}@{since}" if since is not None else None

    def _read(self, mode: str, *, columns, chunk_size, order_by, iterate: bool):
        table = self._table(mode)
        if table is None:
            # No previous run: an empty frame, shaped by the table itself.
            pd = _require_pandas()
            empty = _run_arrow(
                self._client,
                f"SELECT {_select_clause(columns)} FROM '{self._table('current')}' LIMIT 0",
            ).to_pandas()
            return iter([empty]) if iterate else empty
        ref = self.ref
        if mode != "current":
            # `_read_dataframe` builds the handle from the ref; hand it the
            # `@` form directly (a ref holding a dot is used as-is).
            ref = table
        if iterate:
            return _iter_dataframes(self._client, ref, chunk_size or DEFAULT_CHUNK_SIZE, columns, order_by)
        return _read_dataframe(self._client, ref, columns=columns, chunk_size=chunk_size, order_by=order_by)

    def dataframe(
        self,
        mode: str = "current",
        schema: Any = None,
        *,
        columns: Optional[Iterable[str]] = None,
        chunk_size: Optional[int] = None,
        order_by: Optional[str] = None,
    ):
        """The input as a ``pandas.DataFrame`` — ``"current"`` (whole),
        ``"added"`` (appended since the last successful run) or
        ``"previous"`` (as the last run saw it). ``schema`` is accepted for
        symmetry with the outputs; the frame always takes the table's own columns."""
        return self._read(
            mode,
            columns=self.columns if columns is None else columns,
            chunk_size=self.chunk_size if chunk_size is None else chunk_size,
            order_by=self.order_by if order_by is None else order_by,
            iterate=False,
        )

    def iter_dataframes(
        self,
        mode: str = "current",
        *,
        columns: Optional[Iterable[str]] = None,
        chunk_size: Optional[int] = None,
        order_by: Optional[str] = None,
    ) -> Iterator[Any]:
        return self._read(
            mode,
            columns=self.columns if columns is None else columns,
            chunk_size=chunk_size or self.chunk_size or DEFAULT_CHUNK_SIZE,
            order_by=self.order_by if order_by is None else order_by,
            iterate=True,
        )

    def filesystem(self, mode: str = "current") -> FileSystem:
        if mode != "current":
            raise GwenlakeException(
                f"{self.ref}: filesystem({mode!r}) is not available — an Iceberg table's history "
                "is read as rows (dataframe('added')), a files dataset keeps none"
            )
        return super().filesystem()


class _PreviousFileSystem:
    """The output's files as they were before this run wrote any — the file
    side of ``dataframe("previous")``. Read-only, and answering from the
    listing taken then: ``ls`` gives the **files** under ``path`` (every one,
    recursively — there are no directory entries), ``read``/``open`` fetch one
    of them. Writes go through ``output.filesystem()``."""

    def __init__(self, fs: FileSystem, entries: List[Dict[str, Any]]):
        self._fs = fs
        self._entries = entries
        self._paths = {e["path"] for e in entries}

    def ls(self, path: Optional[str] = None, *, glob: Optional[str] = None) -> List[Dict[str, Any]]:
        prefix = (path or "").strip("/")
        selector = _glob_regex(glob) if glob else None
        return [
            e for e in self._entries
            if (not prefix or e["path"].startswith(prefix + "/"))
            and (selector is None or selector.search(e["path"]))
        ]

    files = ls

    def read(self, filepath: str) -> bytes:
        if filepath.strip("/") not in self._paths:
            raise GwenlakeException(f"{filepath!r} was not in the output before this run")
        return self._fs.read(filepath)

    def open(self, filepath: str, mode: str = "r"):
        if any(c in mode for c in "wax+"):
            raise GwenlakeException(
                "the output's previous files are read-only: write through output.filesystem()"
            )
        return io.BytesIO(self.read(filepath))

    def write(self, *args: Any, **kwargs: Any) -> None:
        raise GwenlakeException("the output's previous files are read-only: write through output.filesystem()")

    delete = clear = write


class IncrementalTransformOutput(TransformOutput):
    """An output under ``@incremental``: :class:`TransformOutput` that can read
    itself and whose writes add to it.

    ``dataframe("previous", schema)`` is the dataset as the last successful run
    left it — memoized, and only readable **before** this run's first write
    (afterwards it is no longer what it was, and the handle says so rather than
    answer a mix). While there is nothing yet — the first run, or a run that
    starts over — it is an empty frame shaped by ``schema``.
    ``dataframe("current")`` re-reads the dataset as it is now, this run's
    writes included. ``filesystem("previous")`` is the same for files.

    Writes default to ``modify`` (``APPEND`` into an Iceberg table, one more
    part file in a files dataset, named after the run so runs never overwrite
    each other). ``set_mode("replace")``, or ``mode="replace"`` on a write,
    snapshots instead: the first write of the run replaces, the following ones
    add to it. A run also starts over by itself when the decorator's
    ``semantic_version`` is not the one the output was last written with
    (:attr:`reset`).
    """

    def __init__(self, client: Any, ref: str, *, semantic_version: int = 1, run_id: Optional[str] = None):
        super().__init__(client, ref)
        self.semantic_version = int(semantic_version)
        self.run_id = run_id or _run_id()
        self._mode = "modify"
        self._writes = 0
        self._previous: Dict[Any, Any] = {}
        self._entries: Optional[List[Dict[str, Any]]] = None
        self._has_rows: Optional[bool] = None
        self._reset: Optional[bool] = None
        self._type: Optional[str] = None

    # -- what the output is ------------------------------------------------

    @property
    def dataset_type(self) -> str:
        """``files`` / ``iceberg`` / ``vector``, from the catalog (once)."""
        if self._type is None:
            try:
                info = self._client.datasets.get(self.dataset_id)
            except Exception:
                info = {}
            self._type = (info or {}).get("type") or "files"
        return self._type

    def _check_writable(self) -> None:
        if self.dataset_type == "vector":
            raise GwenlakeException(
                f"{self.ref}: a vector dataset cannot be an incremental output — its table is "
                "rebuilt by the embedding transform, not appended to"
            )

    @property
    def reset(self) -> bool:
        """Whether this run starts over: the decorator's ``semantic_version``
        differs from the one the output was last written with. The build
        engine records that version after each successful build and exports it
        as ``CATALOG_INCREMENTAL``; outside a build, or for an output no
        incremental build has written yet, nothing is recorded and nothing
        starts over."""
        if self._reset is None:
            recorded = _catalog_incremental()
            was = (recorded.get(self.dataset_id) or {}).get("semantic_version") if recorded else None
            self._reset = was is not None and int(was) != self.semantic_version
        return self._reset

    def _require_unwritten(self) -> None:
        if self._writes:
            raise GwenlakeException(
                f"{self.ref}: the output's previous content must be read before the run's "
                "first write — it is no longer what it was"
            )

    def _previous_entries(self) -> List[Dict[str, Any]]:
        """The output's files before this run wrote: taken once, and only
        before the first write."""
        if self._entries is None:
            self._require_unwritten()
            self._entries = [] if self.reset else list(super().filesystem().ls(glob="**"))
        return self._entries

    def _previous_rows(self) -> bool:
        if self._has_rows is None:
            self._require_unwritten()
            self._has_rows = not self.reset and _table_has_rows(self._client, self.ref)
        return self._has_rows

    @property
    def has_previous(self) -> bool:
        """Whether there is anything to read as ``"previous"``: false on the
        first run, on an empty output, and when the run starts over."""
        if self.dataset_type == "iceberg":
            return self._previous_rows()
        return bool(self._previous_entries())

    # -- reading ------------------------------------------------------------

    def dataframe(
        self,
        mode: str = "previous",
        schema: Any = None,
        *,
        columns: Optional[Iterable[str]] = None,
        chunk_size: Optional[int] = DEFAULT_CHUNK_SIZE,
        order_by: Optional[str] = None,
    ):
        """The output as a ``pandas.DataFrame``: ``"previous"`` (see the class)
        or ``"current"``. ``schema`` shapes the empty frame answered while
        there is no previous content; ``columns`` restricts the projection
        (``["path"]`` is all a processed-files log needs)."""
        if mode == "current":
            return _read_dataframe(
                self._client, self.ref, columns=columns, chunk_size=chunk_size, order_by=order_by,
            )
        if mode != "previous":
            raise GwenlakeException(f"unknown output mode {mode!r} (use 'previous' or 'current')")
        key = tuple(columns) if columns is not None else None
        if key not in self._previous:
            if self.has_previous:
                df = _read_dataframe(
                    self._client, self.ref, columns=columns, chunk_size=chunk_size, order_by=order_by,
                )
            else:
                df = _empty_dataframe(schema)
            self._previous[key] = df
        return self._previous[key]

    def filesystem(self, mode: str = "current"):
        """``"current"``: the live :class:`FileSystem` (reads and writes).
        ``"previous"``: the files as they were before this run wrote, read-only."""
        if mode == "current":
            return super().filesystem()
        if mode == "previous":
            return _PreviousFileSystem(super().filesystem(), self._previous_entries())
        raise GwenlakeException(f"unknown output mode {mode!r} (use 'previous' or 'current')")

    # -- writing ------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """``"modify"`` (add to the dataset, the default) or ``"replace"``
        (start it over with this run's writes). Before the first write."""
        if mode not in INCREMENTAL_WRITE_MODES:
            raise ValueError(f"Unsupported mode '{mode}' (use 'modify' or 'replace')")
        if self._writes:
            raise GwenlakeException("set_mode() must be called before the run's first write")
        self._mode = mode

    def _effective_mode(self, mode: Optional[str]) -> str:
        """What this write does, in :class:`TransformOutput`'s terms."""
        mode = mode or self._mode
        if mode == "append":                 # TransformOutput's own spelling
            mode = "modify"
        if mode not in INCREMENTAL_WRITE_MODES:
            raise ValueError(f"Unsupported mode '{mode}' (use 'modify' or 'replace')")
        if self._writes:
            # A run replaces at most once: every write after the first adds to
            # what the run has written so far.
            return "append"
        return "replace" if (mode == "replace" or self.reset) else "append"

    def write_dataframe(
        self,
        df: Any,
        *,
        filename: Optional[str] = None,
        format: str = "parquet",
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write ``df`` into the output — added to it, unless the mode (the
        handle's, or ``mode=`` here) says ``replace``. ``filename`` defaults
        to ``part-<run>-<n>.<ext>``, unique to this run."""
        self._check_writable()
        effective = self._effective_mode(mode)
        if filename is None:
            filename = f"part-{self.run_id}-{self._writes:05d}.{format}"
        result = super().write_dataframe(df, filename=filename, format=format, mode=effective)
        self._writes += 1
        return result

    def write_dataframes(
        self,
        dfs: Iterable[Any],
        *,
        format: str = "parquet",
        mode: Optional[str] = None,
        prefix: str = "part",
    ) -> List[Dict[str, Any]]:
        self._check_writable()
        effective = self._effective_mode(mode)
        results = super().write_dataframes(
            dfs, format=format, mode=effective, prefix=f"{prefix}-{self.run_id}-{self._writes:02d}",
        )
        self._writes += 1
        return results

    def finish(self) -> None:
        """Called by the decorator once the body has returned: a run that
        starts over (:attr:`reset`) and wrote nothing still empties the
        output, so a bumped ``semantic_version`` means what it says even when
        the first run under it finds nothing to write."""
        if self.reset and not self._writes:
            self._check_writable()
            self._client.datasets.empty(self.dataset_id, branch=_catalog_branch())
            self._writes += 1


def _output_handles(
    client: Any, outputs: Dict[str, "Output"], incremental: Optional[Dict[str, Any]],
) -> Dict[str, TransformOutput]:
    """One handle per Output, shared between the body's parameters and the
    decorator's own writes — so a ``set_mode`` in the body is what the
    returned DataFrame is written with."""
    if incremental is None:
        return {name: TransformOutput(client, spec.ref) for name, spec in outputs.items()}
    run_id = _run_id()
    return {
        name: IncrementalTransformOutput(
            client, spec.ref, semantic_version=incremental["semantic_version"], run_id=run_id,
        )
        for name, spec in outputs.items()
    }


def _finish_outputs(handles: Dict[str, TransformOutput]) -> None:
    for handle in handles.values():
        finish = getattr(handle, "finish", None)
        if finish is not None:
            finish()


# ---------------------------------------------------------------------------
# Connections (sources a transform walks itself)
# ---------------------------------------------------------------------------

OPEN_BUFFER_SIZE = 1024 * 1024


class ConnectionFileSystem:
    """Read-only file access to what a connection holds, through the catalog.

    Same surface as :class:`FileSystem` for reading — ``ls`` / ``read`` /
    ``open`` — so a body copying from a connection into an output reads
    naturally::

        for f in fs_in.ls(glob="**/*.pdf"):
            with fs_in.open(f["path"], "rb") as src, fs_out.open(f["path"], "wb") as dst:
                shutil.copyfileobj(src, dst)

    Listings are recursive (every file source lists that way) unless ``depth``
    says how far, and paged by the catalog; ``ls`` follows the pages to the end.
    Paths are relative to the connection's root. There is no ``write``: a
    connection is a source.

    Neither ``read`` nor ``open`` has to move a whole file: ``read`` takes a
    byte range and ``open`` reads lazily, so a large file costs what is read
    of it — the head and the index of a video of several GB, not the video.
    """

    def __init__(self, client: Any, connection_id: str):
        self._client = client
        self._connection_id = connection_id

    def ls(
        self, path: Optional[str] = None, *, glob: Optional[str] = None, depth: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Every file under ``path`` (the whole connection when omitted),
        optionally only those matching ``glob`` (``*`` within a directory,
        ``**`` across). Each entry has ``path``, ``filename``, ``size``,
        ``last_modified`` and ``is_dir``.

        ``depth`` bounds the descent — ``ls`` where the default is ``find``:
        ``depth=1`` is the directory's own entries, its subdirectories among
        them as ``is_dir`` entries whose ``path`` ends in ``/``, to list in turn
        with ``ls(entry["path"], depth=1)``. A source that cannot stop short
        (every one but smb, for now) still answers every file below.
        """
        return list(
            self._client.connections.iter_files(self._connection_id, path=path, glob=glob, max_depth=depth)
        )

    files = ls

    def read(self, filepath: str, offset: int = 0, length: Optional[int] = None) -> bytes:
        """The file's bytes — or ``length`` of them from ``offset`` (the rest of
        the file without ``length``): fewer near the end, ``b""`` at or past
        it. Where the connection's type can seek, only the range moves."""
        return self._client.connections.download(
            self._connection_id, filepath, offset=offset, length=length,
        )

    def open(
        self, filepath: str, mode: str = "rb", *, buffer_size: int = OPEN_BUFFER_SIZE,
    ) -> io.BufferedReader:
        """The file as a seekable binary file that reads it lazily: nothing is
        fetched before the first read, reads that follow one another share one
        response, and ``seek`` moves where the next one starts — so a library
        that wants a file (``zipfile``, ``pyarrow.parquet``, a video demuxer)
        fetches the parts it needs, not the whole file. Close it, or use
        ``with``. Where the connection's type cannot serve a range, the file is
        copied once, whole, to a temporary spool (in memory up to 64 MiB, then
        on disk) and read from there.

        Write modes are refused: a connection is read-only from a transform —
        write into the output's filesystem."""
        if any(c in mode for c in "wax+"):
            raise GwenlakeException(
                f"a connection is read-only: cannot open {filepath!r} for writing — "
                "write into the transform's Output instead"
            )
        from gwenlake.connections import _RelayFile

        return io.BufferedReader(
            _RelayFile(self._client.connections, self._connection_id, filepath), buffer_size,
        )

    def write(self, *args: Any, **kwargs: Any) -> None:
        raise GwenlakeException("a connection is read-only: write into the transform's Output instead")


class TransformConnection:
    """A connection bound to a transform. ``.filesystem()`` walks its files;
    ``.info()`` is the connection row (type, configuration without credentials)."""

    def __init__(self, client: Any, ref: str):
        self._client = client
        self.ref = ref
        self._connection_id: Optional[str] = None
        self._info: Optional[Dict[str, Any]] = None

    @property
    def connection_id(self) -> str:
        if self._connection_id is None:
            self._connection_id = _resolve_connection_id(self._client, self.ref)
        return self._connection_id

    @property
    def id(self) -> str:
        return self.connection_id

    def info(self) -> Dict[str, Any]:
        if self._info is None:
            self._info = self._client.connections.get(self.connection_id)
        return self._info

    @property
    def type(self) -> Optional[str]:
        return self.info().get("type")

    def filesystem(self) -> ConnectionFileSystem:
        return ConnectionFileSystem(self._client, self.connection_id)


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
    model row, using the catalog's ``/mlmodels`` endpoint."""
    alias = ref.split(".", 1)[1] if "." in ref else ref
    project_alias = ref.split(".", 1)[0] if "." in ref else None

    models = _catalog_get(client, "/mlmodels")
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


MAX_COMMIT_BYTES = 95_000_000


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
            method="PATCH", url=f"/mlmodels/{self.id}",
            headers={"Content-Type": "application/json"}, json_data=fields,
        ))
        response.raise_for_status()
        self._info = response.json()
        return self._info

    def file(self, *parts: str) -> str:
        """``os.path.join(model.path, *parts)`` — the usual way to address an
        artifact (``model.file("model.pkl")``)."""
        return os.path.join(self.path, *parts)

    def save(self, source: str, message: Optional[str] = None) -> Dict[str, Any]:
        """Send trained artifacts to the platform, and pin the model to them.

        ``source`` is a file or a directory; its contents land under the
        model's own ``path`` in the repository the model belongs to. A model's
        artifacts live in git -- that is what makes a version a commit, and a
        commit something you can go back to -- so this commits and pushes.

        This is the step a run on the GPU pool does NOT need: there the build
        engine commits whatever the script wrote under ``path``. Training on
        your own machine has no engine behind it, so the upload is explicit.

        Binary weights are carried base64; text files are sent as text so a
        diff on the repository stays readable.
        """
        import base64
        from pathlib import Path

        from gwenlake.client import RequestOptions

        root = Path(source)
        if not root.exists():
            raise GwenlakeException(f"nothing to save at '{source}'")
        files = sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else [root]
        if not files:
            raise GwenlakeException(f"'{source}' holds no file to save")

        info = self.info()
        repository_id = info.get("repository_id")
        if not repository_id:
            raise GwenlakeException(
                f"model '{self.ref}' has no repository: its artifacts have "
                "nowhere to live")
        base = (info.get("path") or "").strip("/")

        changes = []
        for path in files:
            relative = path.name if root.is_file() else str(path.relative_to(root))
            raw = path.read_bytes()
            try:
                changes.append({
                    "path": f"{base}/{relative}" if base else relative,
                    "operation": "upsert",
                    "content": raw.decode("utf-8"),
                    "encoding": "utf-8",
                })
            except UnicodeDecodeError:
                changes.append({
                    "path": f"{base}/{relative}" if base else relative,
                    "operation": "upsert",
                    "content": base64.b64encode(raw).decode("ascii"),
                    "encoding": "base64",
                })

        taille = sum(len(c["content"]) for c in changes)
        if taille > MAX_COMMIT_BYTES:
            gros = sorted(files, key=lambda f: f.stat().st_size, reverse=True)[:3]
            raise GwenlakeException(
                f"{taille / 1e6:.0f} MB encoded, over the {MAX_COMMIT_BYTES / 1e6:.0f} MB "
                f"a git commit accepts. Largest: "
                + ", ".join(f"{f.name} ({f.stat().st_size / 1e6:.0f} MB)" for f in gros)
                + ". Save the weights alone rather than the full training state "
                  "(the optimiser is usually the bulk of it), or keep the big "
                  "artifacts in object storage and commit a pointer.")

        response = self._client._client.send(RequestOptions(
            method="POST", url=f"/git/{repository_id}/commit",
            headers={"Content-Type": "application/json"},
            json_data={
                "ref": info.get("branch") or "main",
                "message": message or f"train: {self.ref}",
                "changes": changes,
            },
        ))
        response.raise_for_status()
        commit = response.json()
        # The commit IS the version: a model card pointing at a sha is a model
        # you can rebuild, where one pointing at a timestamp is not.
        with contextlib.suppress(Exception):
            self.update(version=commit.get("commit"))
        return commit


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

OUTPUT_KEYWORD = "output"


def as_refs(bindings: Dict[str, Any]) -> Dict[str, Any]:
    """Turn plain strings into the Input/Output they obviously mean.

    ``output="crm.clean"`` reads better than ``output=Output("crm.clean")`` and
    says the same thing. The keyword decides the direction: ``output`` is what
    the function produces, everything else is what it reads.

    The explicit form still works, and must -- it is how read options
    (``columns``, ``chunk_size``) and ``Model(...)`` are expressed, which a
    bare string cannot carry.
    """
    resolved: Dict[str, Any] = {}
    for name, value in bindings.items():
        if isinstance(value, str):
            resolved[name] = (Output if name == OUTPUT_KEYWORD else Input)(value)
        else:
            resolved[name] = value
    return resolved


def _split_bindings(
    bindings: Dict[str, Any],
) -> Tuple[Dict[str, Input], Dict[str, Output], Dict[str, Model], Dict[str, Connection]]:
    bindings = as_refs(bindings)
    inputs = {k: v for k, v in bindings.items() if isinstance(v, Input)}
    outputs = {k: v for k, v in bindings.items() if isinstance(v, Output)}
    models = {k: v for k, v in bindings.items() if isinstance(v, Model)}
    connections = {k: v for k, v in bindings.items() if isinstance(v, Connection)}
    unknown = {k: v for k, v in bindings.items() if not isinstance(v, _DatasetRef)}
    if unknown:
        raise TypeError(f"transform bindings must be Input/Model/Connection/Output, got: {list(unknown)}")
    return inputs, outputs, models, connections


def _step(name: str) -> None:
    if os.environ.get("CATALOG_BUILD_ID"):
        print(f"::step::{name}", flush=True)


def transform_df(**bindings: Any) -> Callable:
    """Decorate a function that takes ``Input`` DataFrames (by keyword name) and
    returns what gets written to its ``Output``(s).

    With a single ``Output`` the body returns one DataFrame. With several, it
    returns a ``dict`` keyed by the Output keyword names::

        @transform_df(
            raw=Input("crm.contacts"),
            valid=Output("crm.contacts_valid"),
            rejected=Output("crm.contacts_rejected"),
        )
        def split(raw):
            ok = raw.email.str.contains("@")
            return {"valid": raw[ok], "rejected": raw[~ok]}

    Every declared Output must be present in the dict; a key naming no Output
    is an error. Returning ``None`` writes nothing.

    The decorated function is called as ``fn(client)`` and runs eagerly: it
    reads every input, calls the body, and writes the returned DataFrame(s).
    """
    inputs, outputs, models, connections = _split_bindings(bindings)
    if not outputs:
        raise TypeError("transform_df expects at least one Output, got none")

    def decorator(fn: Callable) -> Callable:
        params = inspect.signature(fn).parameters

        @functools.wraps(fn)
        def wrapper(client: Any) -> Any:
            _step("Read inputs")
            handles = _output_handles(client, outputs, getattr(wrapper, "incremental", None))
            call_kwargs: Dict[str, Any] = {}
            for name in params:
                if name in inputs:
                    spec = inputs[name]
                    call_kwargs[name] = TransformInput(
                        client, spec.ref, **spec.read_options()
                    ).dataframe()
                elif name in models:
                    call_kwargs[name] = TransformModel(client, models[name].ref)
                elif name in connections:
                    call_kwargs[name] = TransformConnection(client, connections[name].ref)
                elif name in outputs:
                    # Tolerated for parity with the user's snippet; the return
                    # value is what actually gets written — through this same
                    # handle, so an incremental body may read its "previous"
                    # or `set_mode` it first.
                    call_kwargs[name] = handles[name]
            _step("Compute")
            result = fn(**call_kwargs)
            if result is None:
                _finish_outputs(handles)
                return result
            if len(outputs) == 1:
                _step("Write outputs")
                handles[next(iter(outputs))].write_dataframe(result)
                _finish_outputs(handles)
                return result
            if not isinstance(result, dict):
                raise TypeError(
                    f"{fn.__name__} declares {len(outputs)} Outputs, so it must return a dict "
                    f"keyed by their names ({', '.join(outputs)}), got {type(result).__name__}"
                )
            unknown = set(result) - set(outputs)
            if unknown:
                raise TypeError(
                    f"{fn.__name__} returned keys matching no Output: {sorted(unknown)} "
                    f"(declared: {', '.join(outputs)})"
                )
            missing = set(outputs) - set(result)
            if missing:
                raise TypeError(
                    f"{fn.__name__} returned no DataFrame for Output(s): {sorted(missing)}"
                )
            _step("Write outputs")
            for name in outputs:
                handles[name].write_dataframe(result[name])
            _finish_outputs(handles)
            return result

        wrapper.kind = "transform_df"
        wrapper.inputs = inputs
        wrapper.outputs = outputs
        wrapper.models = models
        wrapper.connections = connections
        return wrapper

    return decorator


def transform(**bindings: Any) -> Callable:
    """Decorate a function that takes ``TransformInput`` / ``TransformOutput``
    objects (by keyword name). The body is responsible for reading
    (``.dataframe()`` / ``.filesystem()``) and writing (``.write_dataframe()`` /
    ``.filesystem().write()``) explicitly.

    The decorated function is called as ``fn(client)`` and runs eagerly.
    """
    inputs, outputs, models, connections = _split_bindings(bindings)

    def decorator(fn: Callable) -> Callable:
        params = inspect.signature(fn).parameters

        @functools.wraps(fn)
        def wrapper(client: Any) -> Any:
            incremental = getattr(wrapper, "incremental", None)
            handles = _output_handles(client, outputs, incremental)
            input_cls = IncrementalTransformInput if incremental else TransformInput
            call_kwargs: Dict[str, Any] = {}
            for name in params:
                if name in inputs:
                    spec = inputs[name]
                    call_kwargs[name] = input_cls(client, spec.ref, **spec.read_options())
                elif name in models:
                    call_kwargs[name] = TransformModel(client, models[name].ref)
                elif name in connections:
                    call_kwargs[name] = TransformConnection(client, connections[name].ref)
                elif name in outputs:
                    call_kwargs[name] = handles[name]
            _step("Compute")
            result = fn(**call_kwargs)
            _finish_outputs(handles)
            return result

        wrapper.kind = "transform"
        wrapper.inputs = inputs
        wrapper.outputs = outputs
        wrapper.models = models
        wrapper.connections = connections
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
    inputs, outputs, models, connections = _split_bindings(bindings)
    if len(outputs) != 1:
        raise TypeError(f"train expects exactly one Output (the model), got {len(outputs)}")

    def decorator(fn: Callable) -> Callable:
        params = inspect.signature(fn).parameters

        @functools.wraps(fn)
        def wrapper(client: Any) -> Any:
            _step("Read inputs")
            call_kwargs: Dict[str, Any] = {}
            for name in params:
                if name in inputs:
                    call_kwargs[name] = TransformInput(client, inputs[name].ref).dataframe()
                elif name in models:
                    call_kwargs[name] = TransformModel(client, models[name].ref)
                elif name in connections:
                    call_kwargs[name] = TransformConnection(client, connections[name].ref)
                elif name in outputs:
                    call_kwargs[name] = TransformModel(client, outputs[name].ref)
            _step("Train")
            result = fn(**call_kwargs)
            if isinstance(result, dict):
                TransformModel(client, next(iter(outputs.values())).ref).update(metrics=result)
            return result

        wrapper.kind = "train"
        wrapper.inputs = inputs
        wrapper.outputs = outputs
        wrapper.models = models
        wrapper.connections = connections
        return wrapper

    return decorator


def incremental(
    semantic_version: Any = 1,
    *,
    snapshot_inputs: Optional[Iterable[str]] = None,
    require_incremental: bool = False,
    allow_retention: bool = False,
) -> Callable:
    """Make the transform below it incremental — stacked above ``@transform``
    or ``@transform_df``::

        @incremental(semantic_version=1)
        @transform(source=Connection("ops.drop-folder"), log=Output("ops.processed"))
        def ingest(source, log): ...

    Its Outputs become :class:`IncrementalTransformOutput` (``dataframe
    ("previous", schema)``, writes that add), its ``@transform`` inputs
    :class:`IncrementalTransformInput`. A ``@transform_df`` body still gets
    its inputs as DataFrames, whole, and the DataFrame it returns is added to
    the Output rather than replacing it.

    ``semantic_version`` (an integer) is the one knob that acts: bump it and
    the next build starts over — ``"previous"`` is empty and the first write
    replaces. The other three are accepted so a script written against the
    same decorator elsewhere ports as is, but do nothing here:
    ``snapshot_inputs`` because an input is read whole unless the body asks
    for ``dataframe("added")`` itself — the choice is made per read, not per
    decorator, and a files dataset or a connection can only be read whole
    anyway (the catalog keeps a transaction log for Iceberg tables alone);
    ``require_incremental`` because Atlas never silently falls back to a
    snapshot build (only an explicit ``replace`` or a version bump starts
    over, and an ``"added"`` read that has no delta to answer raises rather
    than reading the table whole); ``allow_retention`` because nothing deletes
    from an input behind the transform.

    Not for ``@train``: a model is replaced by its training, never appended to.
    """
    if callable(semantic_version):
        # Bare `@incremental` (no parentheses) is accepted too.
        return incremental()(semantic_version)
    settings = {"semantic_version": int(semantic_version)}

    def decorator(wrapped: Callable) -> Callable:
        if not hasattr(wrapped, "outputs"):
            raise TypeError(
                "@incremental goes above @transform / @transform_df: "
                f"{getattr(wrapped, '__name__', wrapped)!r} carries no Output"
            )
        if getattr(wrapped, "kind", None) == "train":
            raise TypeError("@incremental does not apply to @train: a model is replaced by its training, never appended to")
        wrapped.incremental = settings
        return wrapped

    return decorator


# ---------------------------------------------------------------------------
# Entrypoint dispatch
# ---------------------------------------------------------------------------

def _target_dataset_id() -> Optional[str]:
    """The output dataset this build targets, read out of the storage URL the
    engine exports as ``CATALOG_OUTPUT`` (``.../res.dataset.<uuid>/files/``)."""
    out = os.environ.get("CATALOG_OUTPUT") or os.environ.get("CATALOG_OUTPUT_S3") or ""
    # `.../datasets/res.dataset.<id>/files/` — take the whole path segment rather
    # than assume the id's shape, so an unrecognised id can't quietly degrade
    # into "no target" (which would run every transform in the module).
    match = re.search(r"res\.dataset\.[^/]+", out)
    return match.group(0) if match else None


def _selected_transforms(client: Any, transforms: Tuple[Callable, ...]) -> List[Callable]:
    """The subset of ``transforms`` this build asked for.

    A build targets **one** output, but `uv run` executes the whole module — so a
    file holding several transforms must pick, or it recomputes every one of them
    on every build (and fails the build if any unrelated one fails). The engine
    says which via ``CATALOG_FUNCTION`` (the transform's ``config.function``) or,
    failing that, ``CATALOG_OUTPUT``. Outside a build neither is set and every
    transform runs, which is what you want from a local run.
    """
    wanted_name = (os.environ.get("CATALOG_FUNCTION") or "").strip()
    if wanted_name:
        selected = [fn for fn in transforms if fn.__name__ == wanted_name]
        if not selected:
            available = ", ".join(fn.__name__ for fn in transforms)
            raise GwenlakeException(
                f"CATALOG_FUNCTION='{wanted_name}' matches no transform here (have: {available})"
            )
        return selected

    target = _target_dataset_id()
    if not target:
        return list(transforms)

    selected = []
    for fn in transforms:
        outputs = getattr(fn, "outputs", {}) or {}
        for spec in outputs.values():
            if _resolve_dataset_id(client, spec.ref) == target:
                selected.append(fn)
                break
    if not selected:
        available = ", ".join(fn.__name__ for fn in transforms)
        raise GwenlakeException(
            f"no transform here writes the build's target dataset {target} (have: {available})"
        )
    return selected


def run(client: Any, *transforms: Callable) -> List[Any]:
    """Run the decorated transforms this build targets, and only those.

    Use it as the module entrypoint in place of calling each transform by hand::

        if __name__ == "__main__":
            run(client, transform_train, transform_inference)

    Returns each selected transform's result, in the order given.
    """
    return [fn(client) for fn in _selected_transforms(client, transforms)]