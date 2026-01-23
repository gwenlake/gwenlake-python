import os
from typing import Any, Dict

from gwenlake.factory.core.credentials import Credentials
from gwenlake.factory.core.api_client import ApiClient, RequestInfo


class FilesClient:

    def __init__(self, credentials: Credentials):
        self._credentials = credentials
        self._client = ApiClient(credentials=credentials)
    
    def list(self, dataset_id: str) -> Any:
        response = self._client.call_api(
            RequestInfo(
                method="GET",
                path=f"/datasets/{dataset_id}/files",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")
    
    def get(self, dataset_id: str, filepath: str, branch: str = "main") -> Any:
        response = self._client.call_api(
            RequestInfo(
                method="GET",
                path=f"/datasets/{dataset_id}/files/{filepath}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()

    def content(self, dataset_id: str, filepath: str, branch: str = "main") -> bytes:
        response = self._client.call_api(
            RequestInfo(
                method="GET",
                path=f"/datasets/{dataset_id}/files/{filepath}/content",
                headers={"Accept": "application/octet-stream"},
            ),
        )
        response.raise_for_status()
        return response.json()
    
    def delete(self, dataset_id: str, filepath: str, branch: str = "main") -> bool:
        response = self._client.call_api(
            RequestInfo(
                method="DELETE",
                path=f"/datasets/{dataset_id}/files/{filepath}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True
    
    def upload(self, dataset_id: str, body: bytes, filepath: str, branch: str = "main") -> Dict[str, Any]:
        filename = os.path.basename(filepath)

        response = self._client.call_api(
            RequestInfo(
                method="POST",
                path=f"/datasets/{dataset_id}/files/{filepath}/upload",
                files= {"file": (filename, body)},
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()