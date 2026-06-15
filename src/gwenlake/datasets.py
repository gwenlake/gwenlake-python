from typing import Any, Dict, List

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions


class Datasets:

    def __init__(self, client: ApiClient):
        self._client = client

    def list(self, *, project_id: str = None, organization_id: str = None) -> List[Dict[str, Any]]:
        params = {k: v for k, v in {"project_id": project_id, "organization_id": organization_id}.items() if v}
        response = self._client.send(
            RequestOptions(
                method="GET",
                url="/datasets",
                params=params,
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")

    def get(self, id: str) -> Any:
        response = self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()

    def create(self, data: Dict[str, Any]) -> Any:
        response = self._client.send(
            RequestOptions(
                method="POST",
                url="/datasets",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json_data=data,
            ),
        )
        response.raise_for_status()
        return response.json()

    def delete(self, id: str) -> bool:
        response = self._client.send(
            RequestOptions(
                method="DELETE",
                url=f"/datasets/{id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True


class AsyncDatasets:

    def __init__(self, client: AsyncApiClient):
        self._client = client

    async def list(self, *, project_id: str = None, organization_id: str = None) -> List[Dict[str, Any]]:
        params = {k: v for k, v in {"project_id": project_id, "organization_id": organization_id}.items() if v}
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url="/datasets",
                params=params,
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")

    async def get(self, id: str) -> Any:
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url=f"/datasets/{id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()

    async def create(self, data: Dict[str, Any]) -> Any:
        response = await self._client.send(
            RequestOptions(
                method="POST",
                url="/datasets",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json_data=data,
            ),
        )
        response.raise_for_status()
        return response.json()

    async def delete(self, id: str) -> bool:
        response = await self._client.send(
            RequestOptions(
                method="DELETE",
                url=f"/datasets/{id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True
