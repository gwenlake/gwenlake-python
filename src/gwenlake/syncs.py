"""`/syncs` — copies of an external source into a dataset (`output`), run by
the platform on demand or on a schedule."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Syncs(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/syncs", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, sync_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/syncs/{sync_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `type`, `output` (dataset id), `config`."""
        return self._json("POST", "/syncs", json=data)

    def update(self, sync_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/syncs/{sync_id}", json=data)

    def delete(self, sync_id: str) -> bool:
        return self._ok("DELETE", f"/syncs/{sync_id}")

    def execute(self, sync_id: str, *, branch: Optional[str] = None) -> Any:
        return self._json("POST", f"/syncs/{sync_id}/execute", params={"branch": branch})

class AsyncSyncs(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/syncs", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, sync_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/syncs/{sync_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `type`, `output` (dataset id), `config`."""
        return await self._json("POST", "/syncs", json=data)

    async def update(self, sync_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/syncs/{sync_id}", json=data)

    async def delete(self, sync_id: str) -> bool:
        return await self._ok("DELETE", f"/syncs/{sync_id}")

    async def execute(self, sync_id: str, *, branch: Optional[str] = None) -> Any:
        return await self._json("POST", f"/syncs/{sync_id}/execute", params={"branch": branch})
