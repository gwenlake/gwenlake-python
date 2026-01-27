from typing import Any, Dict
from functools import cached_property

from gwenlake.api_client import ApiClient, RequestOptions
from gwenlake.factory.files import FilesClient


class DatasetsClient:

    def __init__(self, client: ApiClient):
        self._client = client
    
    def get(self, id: str) -> Any:
        response = self._client.call_api(
            RequestOptions(
                method="GET",
                url=f"/datasets/{id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()


    def create(self, data: Dict[str, Any]) -> Any:
        response = self._client.call_api(
            RequestOptions(
                method="POST",
                url="/datasets",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                body=data,
            ),
        )
        response.raise_for_status()
        return response.json()

    def delete(self, id: str) -> bool:
        response = self._client.call_api(
            RequestOptions(
                method="DELETE",
                url=f"/datasets/{id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True
    
    @cached_property
    def files(self):
        return FilesClient(credentials=self._credentials)