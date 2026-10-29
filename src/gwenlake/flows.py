"""`/flows` — the visual pipelines (a graph of nodes from `library`), versioned,
run on demand (`run`, asynchronous: see `run_status`)."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Flows(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/flows", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, flow_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/flows/{flow_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `flow` (the node graph)."""
        return self._json("POST", "/flows", json=data)

    def update(self, flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/flows/{flow_id}", json=data)

    def delete(self, flow_id: str) -> bool:
        return self._ok("DELETE", f"/flows/{flow_id}")

    def library(self) -> List[Dict[str, Any]]:
        """The node types a flow can use."""
        return self._list("GET", "/flows/library")

    def run(self, flow_id: str, *, parameters: Optional[Dict[str, Any]] = None, branch: Optional[str] = None) -> Any:
        return self._json("POST", f"/flows/{flow_id}/run", json=parameters or {}, params={"branch": branch})

    def run_status(self, task_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/flows/runs/{task_id}")

    def versions(self, flow_id: str, *, limit: Optional[int] = None, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/flows/{flow_id}/versions", params={"limit": limit, "branch": branch})

    def version(self, flow_id: str, version_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return self._json("GET", f"/flows/{flow_id}/versions/{version_id}", params={"branch": branch})

class AsyncFlows(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/flows", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, flow_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/flows/{flow_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `flow` (the node graph)."""
        return await self._json("POST", "/flows", json=data)

    async def update(self, flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/flows/{flow_id}", json=data)

    async def delete(self, flow_id: str) -> bool:
        return await self._ok("DELETE", f"/flows/{flow_id}")

    async def library(self) -> List[Dict[str, Any]]:
        """The node types a flow can use."""
        return await self._list("GET", "/flows/library")

    async def run(self, flow_id: str, *, parameters: Optional[Dict[str, Any]] = None, branch: Optional[str] = None) -> Any:
        return await self._json("POST", f"/flows/{flow_id}/run", json=parameters or {}, params={"branch": branch})

    async def run_status(self, task_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/flows/runs/{task_id}")

    async def versions(self, flow_id: str, *, limit: Optional[int] = None, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/flows/{flow_id}/versions", params={"limit": limit, "branch": branch})

    async def version(self, flow_id: str, version_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("GET", f"/flows/{flow_id}/versions/{version_id}", params={"branch": branch})
