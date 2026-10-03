"""`/connections` — the catalog's datasources, and the files behind them.

A connection is a *source* a project declares once (an SMB share, a bucket, a
SharePoint library, a database) and the platform reads on its behalf. This
resource exposes its identity (`list`, `get`) and, for the file-holding kinds,
the **file relay** the catalog puts in front of it: `list_files` /
`iter_files` walk what the connection holds, `download` fetches one file. The
credentials never leave the platform — the catalog authorizes the caller on the
connection (`connections:read`) and reads for them.

This is what a transform declaring ``Connection("proj.share")`` uses under
``.filesystem()`` (see :mod:`gwenlake.transforms`). Read-only by design: a
connection is where data comes from; a transform writes into its output dataset.

Paths are relative to the connection's root, as the catalog serves them, and a
listing is recursive — every file source lists that way.
"""

from typing import Any, Dict, Iterator, List, Optional, AsyncIterator

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions


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

    def download(self, connection_id: str, path: str) -> bytes:
        """One file's bytes, by the path a listing gave."""
        response = self._client.send(RequestOptions(
            method="GET", url=f"/connections/{connection_id}/files/content",
            params={"path": path},
        ))
        response.raise_for_status()
        return response.content


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

    async def download(self, connection_id: str, path: str) -> bytes:
        response = await self._client.send(RequestOptions(
            method="GET", url=f"/connections/{connection_id}/files/content",
            params={"path": path},
        ))
        response.raise_for_status()
        return response.content
