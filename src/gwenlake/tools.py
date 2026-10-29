"""`/tools` — the project's own tools (an HTTP endpoint, a function) an agent
can call; `test` exercises one."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Tools(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/tools", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, tool_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/tools/{tool_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `configuration`."""
        return self._json("POST", "/tools", json=data)

    def update(self, tool_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/tools/{tool_id}", json=data)

    def delete(self, tool_id: str) -> bool:
        return self._ok("DELETE", f"/tools/{tool_id}")

    def restore(self, tool_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/tools/{tool_id}/restore")

    def test(self, tool_id: str) -> Any:
        return self._json("POST", f"/tools/{tool_id}/test")

class AsyncTools(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/tools", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, tool_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/tools/{tool_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `configuration`."""
        return await self._json("POST", "/tools", json=data)

    async def update(self, tool_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/tools/{tool_id}", json=data)

    async def delete(self, tool_id: str) -> bool:
        return await self._ok("DELETE", f"/tools/{tool_id}")

    async def restore(self, tool_id: str) -> Dict[str, Any]:
        return await self._json("POST", f"/tools/{tool_id}/restore")

    async def test(self, tool_id: str) -> Any:
        return await self._json("POST", f"/tools/{tool_id}/test")
