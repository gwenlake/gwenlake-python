from typing import Any, Dict, List, Optional

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions
from gwenlake._resource import AsyncResource as _AR, Resource as _R


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

    def empty(self, id: str, *, branch: Optional[str] = None) -> bool:
        """Remove every row/file of the dataset (`POST /datasets/{id}/empty`),
        on `branch` when given — the whole-dataset form of a snapshot write
        that has nothing to write."""
        response = self._client.send(
            RequestOptions(
                method="POST",
                url=f"/datasets/{id}/empty",
                params={"branch": branch} if branch else {},
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True

    # -- the rest of the dataset routes, in the compact form of `_resource` ----

    def update(self, id: str, data: Dict[str, Any]) -> Any:
        """Partial update of the resource fields: `name`, `slug`, `description`,
        `columns` (the declared schema, only before the table exists), `keys`."""
        return _R(self._client)._json("PATCH", f"/datasets/{id}", json=data)

    def summary(self, id: str) -> Dict[str, Any]:
        """Row count, size, schema and the last snapshot of the dataset."""
        return _R(self._client)._json("GET", f"/datasets/{id}/summary")

    def delete_rows(self, id: str, delete_filter: str, *, branch: Optional[str] = None) -> bool:
        """Remove the rows of an Iceberg dataset matching the row filter, e.g.
        ``source_file = 'x.csv'`` (a DELETE write without a file). Answers
        False when the dataset has no table yet, so there was nothing to delete."""
        response = self._client.send(RequestOptions(
            method="POST", url=f"/datasets/{id}/files",
            params={k: v for k, v in {"mode": "DELETE", "delete_filter": delete_filter, "branch": branch}.items() if v},
            headers={"Accept": "application/json"},
        ))
        if response.status_code == 400 and "no table yet" in response.text:
            return False
        response.raise_for_status()
        return True

    def set_keys(self, id: str, keys: List[str]) -> Any:
        """The identifier columns an UPSERT write matches on."""
        return _R(self._client)._json("PUT", f"/datasets/{id}/keys", json={"keys": keys})

    def branches(self, id: str) -> List[Dict[str, Any]]:
        return _R(self._client)._list("GET", f"/datasets/{id}/branches")

    def delete_branch(self, id: str, branch: str) -> bool:
        return _R(self._client)._ok("DELETE", f"/datasets/{id}/branches/{branch}")

    def promote_branch(self, id: str, branch: str, *, delete: bool = False) -> Any:
        """Make the branch's state the trunk's; `delete` drops the branch after."""
        return _R(self._client)._json("POST", f"/datasets/{id}/branches/{branch}/promote", params={"delete": delete})

    def maintenance(self, id: str, *, older_than_days: Optional[int] = None) -> Any:
        """Compact the Iceberg table and expire its old snapshots."""
        return _R(self._client)._json("POST", f"/datasets/{id}/maintenance", params={"older_than_days": older_than_days})

    def search(self, id: str, *, query: Optional[str] = None, vector: Optional[List[float]] = None,
               limit: Optional[int] = None, where: Optional[str] = None) -> Any:
        """Similarity search over a vector dataset, by text or by vector."""
        body = {k: v for k, v in {"query": query, "vector": vector, "limit": limit, "where": where}.items() if v is not None}
        return _R(self._client)._json("POST", f"/datasets/{id}/search", json=body)

    def resolve(self, ref: str) -> str:
        """The id of ``"<project alias>.<dataset alias>"`` (an id is returned as is)."""
        if ref.startswith("res.dataset."):
            return ref
        return resolve_dataset_id(self._client, ref)


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

    async def empty(self, id: str, *, branch: Optional[str] = None) -> bool:
        response = await self._client.send(
            RequestOptions(
                method="POST",
                url=f"/datasets/{id}/empty",
                params={"branch": branch} if branch else {},
                headers={"Accept": "application/json"},
            ),
        )
        response.raise_for_status()
        return True

    async def update(self, id: str, data: Dict[str, Any]) -> Any:
        return await _AR(self._client)._json("PATCH", f"/datasets/{id}", json=data)

    async def summary(self, id: str) -> Dict[str, Any]:
        return await _AR(self._client)._json("GET", f"/datasets/{id}/summary")

    async def delete_rows(self, id: str, delete_filter: str, *, branch: Optional[str] = None) -> bool:
        response = await self._client.send(RequestOptions(
            method="POST", url=f"/datasets/{id}/files",
            params={k: v for k, v in {"mode": "DELETE", "delete_filter": delete_filter, "branch": branch}.items() if v},
            headers={"Accept": "application/json"},
        ))
        if response.status_code == 400 and "no table yet" in response.text:
            return False
        response.raise_for_status()
        return True

    async def set_keys(self, id: str, keys: List[str]) -> Any:
        return await _AR(self._client)._json("PUT", f"/datasets/{id}/keys", json={"keys": keys})

    async def branches(self, id: str) -> List[Dict[str, Any]]:
        return await _AR(self._client)._list("GET", f"/datasets/{id}/branches")

    async def delete_branch(self, id: str, branch: str) -> bool:
        return await _AR(self._client)._ok("DELETE", f"/datasets/{id}/branches/{branch}")

    async def promote_branch(self, id: str, branch: str, *, delete: bool = False) -> Any:
        return await _AR(self._client)._json("POST", f"/datasets/{id}/branches/{branch}/promote", params={"delete": delete})

    async def maintenance(self, id: str, *, older_than_days: Optional[int] = None) -> Any:
        return await _AR(self._client)._json("POST", f"/datasets/{id}/maintenance", params={"older_than_days": older_than_days})

    async def search(self, id: str, *, query: Optional[str] = None, vector: Optional[List[float]] = None,
                     limit: Optional[int] = None, where: Optional[str] = None) -> Any:
        body = {k: v for k, v in {"query": query, "vector": vector, "limit": limit, "where": where}.items() if v is not None}
        return await _AR(self._client)._json("POST", f"/datasets/{id}/search", json=body)

    async def resolve(self, ref: str) -> str:
        if ref.startswith("res.dataset."):
            return ref
        return await resolve_dataset_id_async(self._client, ref)


def resolve_dataset_id(client: ApiClient, ref: str) -> str:
    """``"<project alias>.<dataset alias>"`` -> dataset id, through the listings."""
    from gwenlake.exceptions import GwenlakeException

    project_alias, _, dataset_alias = ref.partition(".")
    if not dataset_alias:
        raise GwenlakeException(f"'{ref}' is not a '<project>.<dataset>' reference")
    r = _R(client)
    project = next((p for p in r._list("GET", "/filesystem/projects") if p.get("alias") == project_alias or p.get("slug") == project_alias), None)
    if project is None:
        raise GwenlakeException(f"No project '{project_alias}'")
    dataset = next((d for d in r._list("GET", "/datasets", params={"project_id": project["id"]})
                    if d.get("alias") == dataset_alias or d.get("slug") == dataset_alias), None)
    if dataset is None:
        raise GwenlakeException(f"No dataset '{dataset_alias}' in project '{project_alias}'")
    return dataset["id"]


async def resolve_dataset_id_async(client: AsyncApiClient, ref: str) -> str:
    from gwenlake.exceptions import GwenlakeException

    project_alias, _, dataset_alias = ref.partition(".")
    if not dataset_alias:
        raise GwenlakeException(f"'{ref}' is not a '<project>.<dataset>' reference")
    r = _AR(client)
    project = next((p for p in await r._list("GET", "/filesystem/projects") if p.get("alias") == project_alias or p.get("slug") == project_alias), None)
    if project is None:
        raise GwenlakeException(f"No project '{project_alias}'")
    dataset = next((d for d in await r._list("GET", "/datasets", params={"project_id": project["id"]})
                    if d.get("alias") == dataset_alias or d.get("slug") == dataset_alias), None)
    if dataset is None:
        raise GwenlakeException(f"No dataset '{dataset_alias}' in project '{project_alias}'")
    return dataset["id"]
