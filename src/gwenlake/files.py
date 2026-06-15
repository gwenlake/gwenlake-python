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


class Files:

    def __init__(self, client: ApiClient):
        self._client = client

    def list(self, dataset_id: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
        response = self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files",
                params={"path": path} if path else {},
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")

    def download(self, dataset_id: str, filepath: str) -> bytes:
        response = self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files/{filepath}",
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

    def delete(self, dataset_id: str, filepath: str) -> bool:
        response = self._client.send(
            RequestOptions(
                method="DELETE",
                url=f"/datasets/{dataset_id}/files/{filepath}",
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
    ) -> Dict[str, Any]:
        response = self._client.send(
            RequestOptions(
                method="POST",
                url=_upload_url(dataset_id, path),
                files=_multipart(file, filename),
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()


class AsyncFiles:

    def __init__(self, client: AsyncApiClient):
        self._client = client

    async def list(self, dataset_id: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files",
                params={"path": path} if path else {},
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")

    async def download(self, dataset_id: str, filepath: str) -> bytes:
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{dataset_id}/files/{filepath}",
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

    async def delete(self, dataset_id: str, filepath: str) -> bool:
        response = await self._client.send(
            RequestOptions(
                method="DELETE",
                url=f"/datasets/{dataset_id}/files/{filepath}",
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
    ) -> Dict[str, Any]:
        response = await self._client.send(
            RequestOptions(
                method="POST",
                url=_upload_url(dataset_id, path),
                files=_multipart(file, filename),
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()
