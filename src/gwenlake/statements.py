import json
import os
import re
from typing import Any, Dict, Iterator, Optional, Union

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions
from gwenlake.exceptions import GwenlakeException

#: Rows per page when a result is read whole (`iter_arrow`, `to_file`).
DEFAULT_PAGE_ROWS = 50_000

#: A page read scans the dataset server-side before the first byte comes back.
DEFAULT_READ_TIMEOUT = 600.0

#: Output formats `to_file` writes, by file extension.
FILE_FORMATS = {".parquet": "parquet", ".csv": "csv", ".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl"}


# What each `format` sends back, so `Accept` matches what the server will
# actually return (`pyarrow` is an Arrow IPC *file*, not JSON).
_ACCEPT_BY_FORMAT = {
    "json": "application/json",
    "csv": "text/csv",
    "pyarrow": "application/vnd.apache.arrow.file",
}


def _payload(statement, connection_id, format, parameters, limit, mode=None) -> dict:
    payload: Dict[str, Any] = {"statement": statement, "format": format}
    if connection_id:
        payload["connection_id"] = connection_id
    if parameters:
        payload["parameters"] = parameters
    if limit:
        payload["limit"] = limit
    if mode:
        payload["mode"] = mode
    return payload


def _options(statement, connection_id, format, parameters, limit, timeout, mode=None) -> RequestOptions:
    return RequestOptions(
        method="POST",
        url="/sql/statements",
        headers={
            "Accept": _ACCEPT_BY_FORMAT.get(format, "application/json"),
            "Content-Type": "application/json",
        },
        json_data=_payload(statement, connection_id, format, parameters, limit, mode),
        timeout=timeout,
    )


def _arrow(content: bytes):
    import pyarrow as pa

    if not content:
        return pa.table({})
    with pa.ipc.open_file(pa.BufferReader(content)) as reader:
        return reader.read_all()


def _page(statement: str, rows: int, offset: int) -> str:
    """The statement as a page: wrapped, so its own ORDER BY and the server's
    row cap (which only applies to a statement without LIMIT) stay out of the way."""
    return f"SELECT * FROM ({statement.rstrip().rstrip(';')}) AS __page LIMIT {rows} OFFSET {offset}"


def _has_limit(statement: str) -> bool:
    return re.search(r"\blimit\b", statement, re.IGNORECASE) is not None


def file_format(path: str, format: Optional[str] = None) -> str:
    """`format` when given, else the one the file extension says."""
    if format:
        if format not in FILE_FORMATS.values():
            raise GwenlakeException(f"unknown export format '{format}' (parquet, csv, json, jsonl)")
        return format
    ext = os.path.splitext(path)[1].lower()
    if ext not in FILE_FORMATS:
        raise GwenlakeException(f"cannot tell the format of '{path}': use .parquet, .csv, .json or .jsonl, or pass format=")
    return FILE_FORMATS[ext]


class _FileWriter:
    """Writes Arrow tables page after page into one file of `format`."""

    def __init__(self, path: str, format: str):
        self.path, self.format, self.rows = path, format, 0
        self._writer = None
        self._first = True
        self._handle = open(path, "wb")

    def write(self, table) -> None:
        import pyarrow.csv as pacsv
        import pyarrow.parquet as pq

        if self.format == "parquet":
            if self._writer is None:
                self._writer = pq.ParquetWriter(self._handle, table.schema, compression="zstd")
            self._writer.write_table(table)
        elif self.format == "csv":
            pacsv.write_csv(table, self._handle, write_options=pacsv.WriteOptions(include_header=self._first))
        elif self.format == "jsonl":
            for row in table.to_pylist():
                self._handle.write((json.dumps(row, default=str, ensure_ascii=False) + "\n").encode("utf-8"))
        elif self.format == "json":
            # One JSON array, streamed: "[" before the first row, "," between rows, "]" at close.
            for row in table.to_pylist():
                self._handle.write(b"[\n" if self.rows == 0 else b",\n")
                self._handle.write(json.dumps(row, default=str, ensure_ascii=False).encode("utf-8"))
                self.rows += 1
            self._first = False
            return
        self.rows += table.num_rows
        self._first = False

    def close(self) -> None:
        if self.format == "json":
            self._handle.write(b"\n]\n" if self.rows else b"[]\n")
        if self._writer is not None:
            self._writer.close()
        self._handle.close()


class Statements:

    def __init__(self, client: ApiClient):
        self._client = client

    def create(
        self,
        *,
        statement: str,
        connection_id: Optional[str] = None,
        format: str = "json",
        parameters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        timeout: Optional[float] = None,
        mode: Optional[str] = None,
    ) -> Union[Dict[str, Any], bytes]:
        """Run a SQL statement. Without ``connection_id`` it runs in dataset
        mode and must reference ``FROM '<project>.<dataset>'``. ``format="json"``
        returns ``{"object": "list", "data": [...]}``; other formats (``csv``,
        ``pyarrow``) return raw bytes.

        ``timeout`` overrides the client's default for this call — a scan over a
        large dataset can take far longer to answer than an ordinary request.
        ``mode`` picks the engine: ``"duckdb"`` (default) or ``"spark"``.

        Without a LIMIT of its own a statement is capped server-side (1000 rows,
        or ``limit``); use ``iter_arrow`` / ``to_file`` to read a result whole."""
        response = self._client.send(
            _options(statement, connection_id, format, parameters, limit, timeout, mode),
        )
        response.raise_for_status()
        return response.json() if format == "json" else response.content

    def read_arrow(self, statement: str, *, limit: Optional[int] = None, timeout: Optional[float] = DEFAULT_READ_TIMEOUT,
                   mode: Optional[str] = None):
        """One request, the result as a ``pyarrow.Table`` (capped like ``create``)."""
        return _arrow(self.create(statement=statement, format="pyarrow", limit=limit, timeout=timeout, mode=mode))

    def iter_arrow(self, statement: str, *, page_rows: int = DEFAULT_PAGE_ROWS,
                   timeout: Optional[float] = DEFAULT_READ_TIMEOUT, mode: Optional[str] = None) -> Iterator[Any]:
        """The whole result, page by page as ``pyarrow.Table``s: the statement
        is wrapped in LIMIT/OFFSET pages until one comes back short. A statement
        with its own LIMIT is read in one page."""
        if _has_limit(statement):
            table = self.read_arrow(statement, timeout=timeout, mode=mode)
            if table.num_rows:
                yield table
            return
        offset = 0
        while True:
            table = self.read_arrow(_page(statement, page_rows, offset), timeout=timeout, mode=mode)
            if table.num_rows:
                yield table
            if table.num_rows < page_rows:
                return
            offset += page_rows

    def read_all(self, statement: str, **kwargs: Any):
        """The whole result as one ``pyarrow.Table`` (see ``iter_arrow``)."""
        import pyarrow as pa

        pages = list(self.iter_arrow(statement, **kwargs))
        return pa.concat_tables(pages) if pages else pa.table({})

    def to_dataframe(self, statement: str, **kwargs: Any):
        """The whole result as a ``pandas.DataFrame``."""
        return self.read_all(statement, **kwargs).to_pandas()

    def to_file(self, statement: str, path: str, *, format: Optional[str] = None, **kwargs: Any) -> int:
        """Write the whole result to `path` as Parquet, CSV, JSON (one array) or
        JSON Lines, the format taken from the extension unless given. Streams
        page by page, so a result larger than memory is fine. Returns the rows written."""
        writer = _FileWriter(path, file_format(path, format))
        try:
            for table in self.iter_arrow(statement, **kwargs):
                writer.write(table)
        finally:
            writer.close()
        return writer.rows


class AsyncStatements:

    def __init__(self, client: AsyncApiClient):
        self._client = client

    async def create(
        self,
        *,
        statement: str,
        connection_id: Optional[str] = None,
        format: str = "json",
        parameters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        timeout: Optional[float] = None,
        mode: Optional[str] = None,
    ) -> Union[Dict[str, Any], bytes]:
        response = await self._client.send(
            _options(statement, connection_id, format, parameters, limit, timeout, mode),
        )
        response.raise_for_status()
        return response.json() if format == "json" else response.content

    async def read_arrow(self, statement: str, *, limit: Optional[int] = None,
                         timeout: Optional[float] = DEFAULT_READ_TIMEOUT, mode: Optional[str] = None):
        return _arrow(await self.create(statement=statement, format="pyarrow", limit=limit, timeout=timeout, mode=mode))

    async def read_all(self, statement: str, *, page_rows: int = DEFAULT_PAGE_ROWS,
                       timeout: Optional[float] = DEFAULT_READ_TIMEOUT, mode: Optional[str] = None):
        import pyarrow as pa

        if _has_limit(statement):
            return await self.read_arrow(statement, timeout=timeout, mode=mode)
        pages, offset = [], 0
        while True:
            table = await self.read_arrow(_page(statement, page_rows, offset), timeout=timeout, mode=mode)
            if table.num_rows:
                pages.append(table)
            if table.num_rows < page_rows:
                break
            offset += page_rows
        return pa.concat_tables(pages) if pages else pa.table({})

    async def to_file(self, statement: str, path: str, *, format: Optional[str] = None, **kwargs: Any) -> int:
        writer = _FileWriter(path, file_format(path, format))
        try:
            writer.write(await self.read_all(statement, **kwargs))
        finally:
            writer.close()
        return writer.rows
