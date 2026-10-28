import os
from typing import Any, Dict, List, Optional, Union

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions


def _multipart(file: Union[str, bytes], filename: Optional[str]) -> dict:
    """Build the httpx ``files=`` mapping from a local path or raw bytes."""
    if isinstance(file, (bytes, bytearray)):
        if not filename:
            raise ValueError("filename is required when uploading raw bytes")
        return {"file": (filename, bytes(file))}
    with open(file, "rb") as f:
        content = f.read()
    return {"file": (filename or os.path.basename(file), content)}


def _upload_url(dataset_id: str, path: Optional[str]) -> str:
    base = f"/datasets/{dataset_id}/files"
    return f"{base}/{path}" if path else base


def _branch_params(**values: Optional[str]) -> Dict[str, str]:
    """Query parameters from the optional ones a file call takes (`path`,
    `branch`): only those set, so trunk requests stay exactly what they were."""
    return {k: v for k, v in values.items() if v}


class Files:

    def __init__(self, client: ApiClient):
        self._client = client

    def list(
        self, dataset_id: str, path: Optional[str] = None, *, branch: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # `branch` names an Iceberg data branch. A files dataset has one
        # version and lists it whatever the value.
        response = self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files",
                params=_branch_params(path=path, branch=branch),
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")

    def download(self, dataset_id: str, filepath: str, *, branch: Optional[str] = None) -> bytes:
        response = self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files/{filepath}",
                params=_branch_params(branch=branch),
            ),
        )
        response.raise_for_status()
        return response.content

    def presigned_url(self, dataset_id: str, filepath: str, expires_in: int = 3600) -> Dict[str, Any]:
        response = self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files/{filepath}/presigned-url",
                params={"expires_in": expires_in},
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()

    def delete(self, dataset_id: str, filepath: str, *, branch: Optional[str] = None) -> bool:
        # `branch` names an Iceberg data branch. A files dataset has one
        # version: a delete naming another branch is refused (400).
        response = self._client.send(
            RequestOptions(
                method="DELETE",
                url=f"/datasets/{dataset_id}/files/{filepath}",
                params=_branch_params(branch=branch),
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True

    def upload(
        self,
        dataset_id: str,
        file: Union[str, bytes],
        *,
        path: Optional[str] = None,
        filename: Optional[str] = None,
        mode: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        # `mode` (APPEND/SNAPSHOT/…) and `branch` steer Iceberg-dataset writes;
        # they are ignored by files datasets.
        params = {k: v for k, v in {"mode": mode, "branch": branch}.items() if v}
        response = self._client.send(
            RequestOptions(
                method="POST",
                url=_upload_url(dataset_id, path),
                params=params,
                files=_multipart(file, filename),
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()


class AsyncFiles:

    def __init__(self, client: AsyncApiClient):
        self._client = client

    async def list(
        self, dataset_id: str, path: Optional[str] = None, *, branch: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files",
                params=_branch_params(path=path, branch=branch),
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")

    async def download(self, dataset_id: str, filepath: str, *, branch: Optional[str] = None) -> bytes:
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files/{filepath}",
                params=_branch_params(branch=branch),
            ),
        )
        response.raise_for_status()
        return response.content

    async def presigned_url(self, dataset_id: str, filepath: str, expires_in: int = 3600) -> Dict[str, Any]:
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files/{filepath}/presigned-url",
                params={"expires_in": expires_in},
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()

    async def delete(self, dataset_id: str, filepath: str, *, branch: Optional[str] = None) -> bool:
        response = await self._client.send(
            RequestOptions(
                method="DELETE",
                url=f"/datasets/{dataset_id}/files/{filepath}",
                params=_branch_params(branch=branch),
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True

    async def upload(
        self,
        dataset_id: str,
        file: Union[str, bytes],
        *,
        path: Optional[str] = None,
        filename: Optional[str] = None,
        mode: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        # `mode` (APPEND/SNAPSHOT/…) and `branch` steer Iceberg-dataset writes;
        # they are ignored by files datasets.
        params = {k: v for k, v in {"mode": mode, "branch": branch}.items() if v}
        response = await self._client.send(
            RequestOptions(
                method="POST",
                url=_upload_url(dataset_id, path),
                params=params,
                files=_multipart(file, filename),
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()
