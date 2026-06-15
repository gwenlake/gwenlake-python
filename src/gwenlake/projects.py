from typing import Any, Dict, List

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions


class Projects:

    def __init__(self, client: ApiClient):
        self._client = client

    def list(self, *, organization_id: str = None) -> List[Dict[str, Any]]:
        params = {"organization_id": organization_id} if organization_id else {}
        response = self._client.send(
            RequestOptions(
                method="GET",
                url="/filesystem/projects",
                params=params,
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")

    def get(self, project_id: str) -> Any:
        response = self._client.send(
            RequestOptions(
                method="GET",
                url=f"/filesystem/projects/{project_id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()

    def create(self, data: Dict[str, Any]) -> Any:
        response = self._client.send(
            RequestOptions(
                method="POST",
                url="/filesystem/projects",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json_data=data,
            ),
        )
        response.raise_for_status()
        return response.json()

    def update(self, project_id: str, data: Dict[str, Any]) -> Any:
        response = self._client.send(
            RequestOptions(
                method="PATCH",
                url=f"/filesystem/projects/{project_id}",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json_data=data,
            ),
        )
        response.raise_for_status()
        return response.json()

    def delete(self, project_id: str) -> bool:
        response = self._client.send(
            RequestOptions(
                method="DELETE",
                url=f"/filesystem/projects/{project_id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True

    def datasets(self, project_id: str) -> List[Dict[str, Any]]:
        response = self._client.send(
            RequestOptions(
                method="GET",
                url=f"/filesystem/projects/{project_id}/datasets",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")


class AsyncProjects:

    def __init__(self, client: AsyncApiClient):
        self._client = client

    async def list(self, *, organization_id: str = None) -> List[Dict[str, Any]]:
        params = {"organization_id": organization_id} if organization_id else {}
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url="/filesystem/projects",
                params=params,
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")

    async def get(self, project_id: str) -> Any:
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url=f"/filesystem/projects/{project_id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json()

    async def create(self, data: Dict[str, Any]) -> Any:
        response = await self._client.send(
            RequestOptions(
                method="POST",
                url="/filesystem/projects",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json_data=data,
            ),
        )
        response.raise_for_status()
        return response.json()

    async def update(self, project_id: str, data: Dict[str, Any]) -> Any:
        response = await self._client.send(
            RequestOptions(
                method="PATCH",
                url=f"/filesystem/projects/{project_id}",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json_data=data,
            ),
        )
        response.raise_for_status()
        return response.json()

    async def delete(self, project_id: str) -> bool:
        response = await self._client.send(
            RequestOptions(
                method="DELETE",
                url=f"/filesystem/projects/{project_id}",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True

    async def datasets(self, project_id: str) -> List[Dict[str, Any]]:
        response = await self._client.send(
            RequestOptions(
                method="GET",
                url=f"/filesystem/projects/{project_id}/datasets",
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return response.json().get("data")
