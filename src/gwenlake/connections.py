"""`/connections` — the catalog's datasources, and the files behind them.

A connection is a *source* a project declares once (an SMB share, a bucket, a
SharePoint library, a database) and the platform reads on its behalf. This
resource exposes its identity (`list`, `get`) and, for the file-holding kinds,
the **file relay** the catalog puts in front of it: `list_files` /
`iter_files` walk what the connection holds, `download` fetches one file — or
a byte range of it. The credentials never leave the platform — the catalog
authorizes the caller on the connection (`connections:read`) and reads for them.

This is what a transform declaring ``Connection("proj.share")`` uses under
``.filesystem()`` (see :mod:`gwenlake.transforms`). Read-only by design: a
connection is where data comes from; a transform writes into its output dataset.

Paths are relative to the connection's root, as the catalog serves them, and a
listing is recursive — every file source lists that way.

A byte range travels as a standard ``Range`` header, and the relay answers it
three ways: 206 with the range where the connection's type can seek (an SMB
share, a bucket), 416 when the range starts at or past the end of the file, and
200 with the whole file where the type cannot seek or the catalog predates
ranges — a server may ignore ``Range`` (RFC 9110 §14.2). `download` takes all
three and keeps only its range of a whole file; the lazy file under
``.filesystem().open()`` (`_RelayFile`) copies a whole file once and reads the
copy.
"""

import io
import re
import tempfile
from typing import IO, Any, Dict, Iterator, List, Optional, AsyncIterator, Tuple

import httpx

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions
from gwenlake.exceptions import GwenlakeException

SPOOL_MEMORY_BYTES = 64 * 1024 * 1024

_SPOOL_READ_BYTES = 1024 * 1024

_CONTENT_RANGE = re.compile(r"bytes\s+(?:(\d+)-\d+|\*)/(\d+|\*)", re.IGNORECASE)


def _list_params(
    project_id: Optional[str], organization_id: Optional[str],
) -> Dict[str, Any]:
    return {k: v for k, v in {"project_id": project_id, "organization_id": organization_id}.items() if v}


def _files_params(
    path: Optional[str], glob: Optional[str], start_after: Optional[str], limit: Optional[int],
) -> Dict[str, Any]:
    return {
        k: v for k, v in
        {"path": path, "glob": glob, "start_after": start_after, "limit": limit}.items()
        if v
    }


def _is_range(offset: int, length: Optional[int]) -> bool:
    """Whether a `download` is for a byte range rather than the whole file —
    after checking that ``offset`` and ``length`` make one."""
    if offset < 0:
        raise ValueError(f"offset must be >= 0, got {offset}")
    if length is not None and length < 1:
        raise ValueError(f"length must be >= 1, got {length}")
    return offset > 0 or length is not None


def _range_header(offset: int, length: Optional[int]) -> str:
    """``Range`` for ``length`` bytes from ``offset``, or for the rest of the
    file when ``length`` is None."""
    return f"bytes={offset}-" if length is None else f"bytes={offset}-{offset + length - 1}"


def _content_range(response: httpx.Response) -> Tuple[Optional[int], Optional[int]]:
    """``(first byte, file size)`` from a 206's or a 416's ``Content-Range``,
    None for what it does not say."""
    match = _CONTENT_RANGE.fullmatch(response.headers.get("content-range", "").strip())
    if match is None:
        return None, None
    first, size = match.groups()
    return (None if first is None else int(first)), (None if size == "*" else int(size))


def _check_start(response: httpx.Response, offset: int, path: str) -> None:
    """A 206 must hold the range that was asked: bytes placed at the wrong
    offset would be worse than an error."""
    first, _ = _content_range(response)
    if first is not None and first != offset:
        raise GwenlakeException(
            f"asked for {path!r} from byte {offset}, the relay answered from byte {first}"
        )


class _Slice:
    """Bytes ``[offset, offset + length)`` of a whole file read chunk by chunk:
    what a ranged `download` keeps when the relay answers with the whole file.
    Only the slice is held, and `feed` says when it is complete so the reader
    can stop there instead of reading the file to its end."""

    def __init__(self, offset: int, length: Optional[int]):
        self._skip = offset
        self._left = length
        self._data = bytearray()

    def feed(self, chunk: bytes) -> bool:
        """Keeps what of ``chunk`` falls in the slice; True once it is complete."""
        if self._skip:
            skipped = min(self._skip, len(chunk))
            chunk, self._skip = chunk[skipped:], self._skip - skipped
        if self._left is not None:
            chunk = chunk[:self._left]
            self._left -= len(chunk)
        self._data += chunk
        return self._left == 0

    def value(self) -> bytes:
        return bytes(self._data)


class Connections:

    def __init__(self, client: ApiClient):
        self._client = client

    def list(
        self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """The connections the caller can see — identity and `type`, no
        configuration (that is one call per row: use `get`)."""
        response = self._client.send(RequestOptions(
            method="GET", url="/connections",
            params=_list_params(project_id, organization_id),
            headers={"Accept": "application/json"},
        ))
        response.raise_for_status()
        return response.json().get("data")

    def get(self, connection_id: str) -> Dict[str, Any]:
        response = self._client.send(RequestOptions(
            method="GET", url=f"/connections/{connection_id}",
            headers={"Accept": "application/json"},
        ))
        response.raise_for_status()
        return response.json()

    def list_files(
        self, connection_id: str, *, path: Optional[str] = None, glob: Optional[str] = None,
        start_after: Optional[str] = None, limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """One page of the connection's files: ``{"data": [...], "next_start_after": ...}``.
        Each entry carries ``path`` (relative to the connection's root),
        ``filename``, ``size`` and ``last_modified``. ``glob`` keeps only the
        matching paths (``*`` within a directory, ``**`` across)."""
        response = self._client.send(RequestOptions(
            method="GET", url=f"/connections/{connection_id}/files",
            params=_files_params(path, glob, start_after, limit),
            headers={"Accept": "application/json"},
        ))
        response.raise_for_status()
        return response.json()

    def iter_files(
        self, connection_id: str, *, path: Optional[str] = None, glob: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Every file, following the pages to the end."""
        start_after: Optional[str] = None
        while True:
            page = self.list_files(
                connection_id, path=path, glob=glob, start_after=start_after, limit=page_size,
            )
            entries = page.get("data") or []
            yield from entries
            start_after = page.get("next_start_after")
            if not start_after or not entries:
                return

    def download(
        self, connection_id: str, path: str, *, offset: int = 0, length: Optional[int] = None,
    ) -> bytes:
        """One file's bytes, by the path a listing gave.

        With ``offset`` and/or ``length``, only ``length`` bytes from ``offset``
        (the rest of the file without ``length``), as ``seek(offset)`` then
        ``read(length)`` would return them: fewer near the end, ``b""`` at or
        past it. Where the connection's type can seek, the relay sends that
        range alone; where it cannot, it sends the whole file, and the range is
        cut from it as it streams by — the response is closed as soon as the
        range is in, so the file is never held whole."""
        if not _is_range(offset, length):
            response = self._client.send(RequestOptions(
                method="GET", url=f"/connections/{connection_id}/files/content",
                params={"path": path},
            ))
            response.raise_for_status()
            return response.content
        response = self._open_range(connection_id, path, offset=offset, length=length)
        try:
            if response.status_code == 416:
                return b""
            if response.status_code == 206:
                _check_start(response, offset, path)
                return response.read()
            part = _Slice(offset, length)
            for chunk in response.iter_bytes():
                if part.feed(chunk):
                    break
            return part.value()
        finally:
            response.close()

    def _open_range(
        self, connection_id: str, path: str, *, offset: int, length: Optional[int] = None,
    ) -> httpx.Response:
        """The relay's answer to a ``Range`` request, its body still unread:
        206 (the range), 416 (it starts at or past the end of the file) or any
        other 2xx (the whole file: the range was ignored). An error raises as
        `raise_for_status` does, its body read for the exception to carry. The
        caller closes the response."""
        response = self._client.send_stream(RequestOptions(
            method="GET", url=f"/connections/{connection_id}/files/content",
            params={"path": path}, headers={"Range": _range_header(offset, length)},
        ))
        if response.status_code != 416 and not response.is_success:
            try:
                response.read()
            finally:
                response.close()
            response.raise_for_status()
        return response


class AsyncConnections:

    def __init__(self, client: AsyncApiClient):
        self._client = client

    async def list(
        self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        response = await self._client.send(RequestOptions(
            method="GET", url="/connections",
            params=_list_params(project_id, organization_id),
            headers={"Accept": "application/json"},
        ))
        response.raise_for_status()
        return response.json().get("data")

    async def get(self, connection_id: str) -> Dict[str, Any]:
        response = await self._client.send(RequestOptions(
            method="GET", url=f"/connections/{connection_id}",
            headers={"Accept": "application/json"},
        ))
        response.raise_for_status()
        return response.json()

    async def list_files(
        self, connection_id: str, *, path: Optional[str] = None, glob: Optional[str] = None,
        start_after: Optional[str] = None, limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        response = await self._client.send(RequestOptions(
            method="GET", url=f"/connections/{connection_id}/files",
            params=_files_params(path, glob, start_after, limit),
            headers={"Accept": "application/json"},
        ))
        response.raise_for_status()
        return response.json()

    async def iter_files(
        self, connection_id: str, *, path: Optional[str] = None, glob: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        start_after: Optional[str] = None
        while True:
            page = await self.list_files(
                connection_id, path=path, glob=glob, start_after=start_after, limit=page_size,
            )
            entries = page.get("data") or []
            for entry in entries:
                yield entry
            start_after = page.get("next_start_after")
            if not start_after or not entries:
                return

    async def download(
        self, connection_id: str, path: str, *, offset: int = 0, length: Optional[int] = None,
    ) -> bytes:
        """See `Connections.download`."""
        if not _is_range(offset, length):
            response = await self._client.send(RequestOptions(
                method="GET", url=f"/connections/{connection_id}/files/content",
                params={"path": path},
            ))
            response.raise_for_status()
            return response.content
        response = await self._open_range(connection_id, path, offset=offset, length=length)
        try:
            if response.status_code == 416:
                return b""
            if response.status_code == 206:
                _check_start(response, offset, path)
                return await response.aread()
            part = _Slice(offset, length)
            async for chunk in response.aiter_bytes():
                if part.feed(chunk):
                    break
            return part.value()
        finally:
            await response.aclose()

    async def _open_range(
        self, connection_id: str, path: str, *, offset: int, length: Optional[int] = None,
    ) -> httpx.Response:
        """See `Connections._open_range`; the caller `aclose()`s the response."""
        response = await self._client.send_stream(RequestOptions(
            method="GET", url=f"/connections/{connection_id}/files/content",
            params={"path": path}, headers={"Range": _range_header(offset, length)},
        ))
        if response.status_code != 416 and not response.is_success:
            try:
                await response.aread()
            finally:
                await response.aclose()
            response.raise_for_status()
        return response


class _RelayFile(io.RawIOBase):
    """A connection's file read through the relay by byte range: the raw file
    under `ConnectionFileSystem.open`, which buffers it (`io.BufferedReader`).

    It holds at most one response, positioned at `tell()`. Reads that follow
    one another consume it — a pass over the file is one request, whatever its
    size — and a seek elsewhere drops it, the next read asking for
    ``bytes={pos}-``. Every answer to a range tells the file's size (the total
    of ``Content-Range``), so a read at or past the end costs no request and
    ``SEEK_END`` costs a one-byte one only before the first read. A response
    that breaks off part-way is resumed once, from where it broke.

    A relay that answers a range with the whole file (200: the connection's
    type cannot seek, or the catalog predates ranges) is taken at its word,
    once: the file is copied into a spooled temporary file — in memory up to
    `SPOOL_MEMORY_BYTES`, on disk past it — and every read is served from it.
    """

    def __init__(self, connections: Connections, connection_id: str, path: str):
        super().__init__()
        self._connections = connections
        self._connection_id = connection_id
        self._path = path
        self._pos = 0
        self._size: Optional[int] = None
        self._response: Optional[httpx.Response] = None
        self._chunks: Optional[Iterator[bytes]] = None
        self._pending = memoryview(b"")
        self._spool: Optional[IO[bytes]] = None

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        self._checkClosed()
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        self._checkClosed()
        if whence == io.SEEK_SET:
            pos = offset
        elif whence == io.SEEK_CUR:
            pos = self._pos + offset
        elif whence == io.SEEK_END:
            pos = self._file_size() + offset
        else:
            raise ValueError(f"invalid whence ({whence}, should be 0, 1 or 2)")
        if pos < 0:
            raise ValueError(f"negative seek position {pos}")
        if pos != self._pos:
            self._drop()
            self._pos = pos
        return pos

    def readinto(self, buffer: Any) -> int:
        self._checkClosed()
        view = memoryview(buffer).cast("B")
        if len(view) and not self._pending:
            self._pending = memoryview(self._next_chunk())
        n = min(len(view), len(self._pending))
        view[:n] = self._pending[:n]
        self._pending = self._pending[n:]
        self._pos += n
        return n

    def readall(self) -> bytes:
        self._checkClosed()
        parts = [bytes(self._pending)]
        self._pos += len(self._pending)
        self._pending = memoryview(b"")
        while chunk := self._next_chunk():
            parts.append(chunk)
            self._pos += len(chunk)
        return b"".join(parts)

    def close(self) -> None:
        try:
            self._drop()
            if self._spool is not None:
                self._spool.close()
                self._spool = None
        finally:
            super().close()

    def _next_chunk(self) -> bytes:
        """The bytes that follow the current position, as many as the source
        hands over at once; b"" at the end of the file."""
        resumed = False
        while True:
            if self._spool is not None:
                self._spool.seek(self._pos)
                return self._spool.read(_SPOOL_READ_BYTES)
            if self._size is not None and self._pos >= self._size:
                self._drop()
                return b""
            if self._response is None and not self._open():
                return b""
            try:
                if self._response.status_code != 206:
                    self._copy_whole()
                    continue
                chunk = next(self._chunks, b"")
                if chunk:
                    return chunk
                if self._size is not None and self._pos < self._size:
                    raise httpx.RemoteProtocolError(
                        f"the relay ended {self._path!r} at byte {self._pos} of {self._size}"
                    )
                self._drop()
                return b""
            except httpx.TransportError:
                self._drop()
                if resumed:
                    raise
                resumed = True

    def _open(self) -> bool:
        """Asks for the file from the current position on; False when the relay
        says there is nothing there (416)."""
        response = self._connections._open_range(self._connection_id, self._path, offset=self._pos)
        first, size = _content_range(response)
        if size is not None and response.status_code in (206, 416):
            self._size = size
        if response.status_code == 416:
            response.close()
            return False
        if response.status_code == 206:
            try:
                _check_start(response, self._pos, self._path)
            except GwenlakeException:
                response.close()
                raise
        self._response, self._chunks = response, response.iter_bytes()
        return True

    def _copy_whole(self) -> None:
        """The relay answered with the whole file: copy it into the spool, which
        serves every read from now on."""
        spool = tempfile.SpooledTemporaryFile(max_size=SPOOL_MEMORY_BYTES)
        try:
            for chunk in self._chunks:
                spool.write(chunk)
        except BaseException:
            spool.close()
            raise
        finally:
            self._drop()
        self._spool, self._size = spool, spool.tell()

    def _file_size(self) -> int:
        """The size an answer to a range gave — asked with a one-byte range when
        none has come yet."""
        if self._size is None and self._spool is None:
            self._drop()
            response = self._connections._open_range(
                self._connection_id, self._path, offset=0, length=1,
            )
            if response.status_code in (206, 416):
                response.close()
                self._size = _content_range(response)[1]
            else:
                self._response, self._chunks = response, response.iter_bytes()
                self._copy_whole()
        if self._size is None:
            raise GwenlakeException(f"the relay did not tell the size of {self._path!r}")
        return self._size

    def _drop(self) -> None:
        """Lets the response go, if one is open: the next read asks again, from
        the current position."""
        response, self._response, self._chunks = self._response, None, None
        self._pending = memoryview(b"")
        if response is not None:
            response.close()
