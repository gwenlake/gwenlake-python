"""`/lineage` and the lineage part of `/orchestration` — the workflow graph.

`graph` is the general form: the nodes and edges around any resource, in one
direction or both. `dataset`, `job`, `run` and `project` are the catalog's
focused views. Data **branches** fork a whole lineage cone onto an Iceberg
branch (`create_branch`), build on it, and promote it back (`merge_branch`).
`positions` are the layout the workflow view remembers for a project.
"""

from typing import Any, Dict, Optional

from gwenlake._resource import AsyncResource, Resource


class Lineage(Resource):

    def graph(self, resource_id: str, *, direction: Optional[str] = None) -> Dict[str, Any]:
        """Nodes and edges around `resource_id`; `direction` = upstream | downstream | both."""
        return self._json("GET", f"/orchestration/lineage/{resource_id}", params={"direction": direction})

    def dataset(self, dataset_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/lineage/datasets/{dataset_id}")

    def job(self, producer_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/lineage/jobs/{producer_id}")

    def run(self, build_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/lineage/runs/{build_id}")

    def project(self, project_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/lineage/projects/{project_id}")

    def propagate(self, root_id: str, *, branch: Optional[str] = None) -> Any:
        """Re-derive what depends on `root_id` (asynchronous: answers a task)."""
        return self._json("POST", f"/orchestration/lineage/{root_id}/propagate", params={"branch": branch})

    def create_branch(self, root_id: str, name: str, *, from_branch: str = "main", build: bool = False) -> Dict[str, Any]:
        """Fork the lineage of `root_id` onto Iceberg branch `name`; `build` also builds it there."""
        return self._json("POST", "/orchestration/branches",
                          json={"root_id": root_id, "name": name, "from_branch": from_branch, "build": build})

    def merge_branch(self, root_id: str, name: str, *, delete_branch: bool = False) -> Dict[str, Any]:
        """Promote branch `name` into trunk across the lineage cone of `root_id`."""
        return self._json("POST", "/orchestration/branches/merge",
                          json={"root_id": root_id, "name": name, "delete_branch": delete_branch})

    def delete_branch(self, root_id: str, name: str) -> Any:
        return self._json("DELETE", f"/orchestration/branches/{name}", params={"root_id": root_id})

    def positions(self, project_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/orchestration/projects/{project_id}/positions")

    def set_positions(self, project_id: str, positions: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PUT", f"/orchestration/projects/{project_id}/positions", json={"positions": positions})

    def clear_positions(self, project_id: str) -> bool:
        return self._ok("DELETE", f"/orchestration/projects/{project_id}/positions")


class AsyncLineage(AsyncResource):

    async def graph(self, resource_id: str, *, direction: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("GET", f"/orchestration/lineage/{resource_id}", params={"direction": direction})

    async def dataset(self, dataset_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/lineage/datasets/{dataset_id}")

    async def job(self, producer_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/lineage/jobs/{producer_id}")

    async def run(self, build_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/lineage/runs/{build_id}")

    async def project(self, project_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/lineage/projects/{project_id}")

    async def propagate(self, root_id: str, *, branch: Optional[str] = None) -> Any:
        return await self._json("POST", f"/orchestration/lineage/{root_id}/propagate", params={"branch": branch})

    async def create_branch(self, root_id: str, name: str, *, from_branch: str = "main", build: bool = False) -> Dict[str, Any]:
        return await self._json("POST", "/orchestration/branches",
                                json={"root_id": root_id, "name": name, "from_branch": from_branch, "build": build})

    async def merge_branch(self, root_id: str, name: str, *, delete_branch: bool = False) -> Dict[str, Any]:
        return await self._json("POST", "/orchestration/branches/merge",
                                json={"root_id": root_id, "name": name, "delete_branch": delete_branch})

    async def delete_branch(self, root_id: str, name: str) -> Any:
        return await self._json("DELETE", f"/orchestration/branches/{name}", params={"root_id": root_id})

    async def positions(self, project_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/orchestration/projects/{project_id}/positions")

    async def set_positions(self, project_id: str, positions: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PUT", f"/orchestration/projects/{project_id}/positions", json={"positions": positions})

    async def clear_positions(self, project_id: str) -> bool:
        return await self._ok("DELETE", f"/orchestration/projects/{project_id}/positions")
