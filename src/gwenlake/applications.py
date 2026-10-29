"""`/applications` — the deployed apps of a project, from a template and a
configuration."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Applications(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/applications", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, application_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/applications/{application_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `template`, `configuration`."""
        return self._json("POST", "/applications", json=data)

    def update(self, application_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/applications/{application_id}", json=data)

    def delete(self, application_id: str) -> bool:
        return self._ok("DELETE", f"/applications/{application_id}")

class AsyncApplications(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/applications", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, application_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/applications/{application_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `template`, `configuration`."""
        return await self._json("POST", "/applications", json=data)

    async def update(self, application_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/applications/{application_id}", json=data)

    async def delete(self, application_id: str) -> bool:
        return await self._ok("DELETE", f"/applications/{application_id}")
