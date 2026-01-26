from typing import Any, Dict
from functools import cached_property

from gwenlake.core.credentials import Credentials
from gwenlake.core.api_client import ApiClient, RequestInfo
from gwenlake.factory.files import FilesClient


class DatasetsClient:

    def __init__(self, credentials: Credentials):
        self._credentials = credentials
        self._client = ApiClient(credentials=credentials, prefix="/api/v1")
    
    def get(self, id: str) -> Any:
        response = self._client.call_api(
            RequestInfo(
                method="GET",
                path=f"/datasets/{id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()


    def create(self, data: Dict[str, Any]) -> Any:
        response = self._client.call_api(
            RequestInfo(
                method="POST",
                path="/datasets",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                body=data,
            ),
        )
        response.raise_for_status()
        return response.json()

    def delete(self, id: str) -> bool:
        response = self._client.call_api(
            RequestInfo(
                method="DELETE",
                path=f"/datasets/{id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True
    
    @cached_property
    def files(self):
        return FilesClient(credentials=self._credentials)