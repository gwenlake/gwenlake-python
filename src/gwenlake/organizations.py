"""`/organizations` — the tenant: its settings (storage, git, iceberg), its
members and roles, its projects and API keys, its LLM usage."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Organizations(Resource):

    def list(self) -> List[Dict[str, Any]]:
        return self._list("GET", "/organizations")

    def get(self, organization_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/organizations/{organization_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `description`, `storage`, `git`, `iceberg`."""
        return self._json("POST", "/organizations", json=data)

    def update(self, organization_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/organizations/{organization_id}", json=data)

    def delete(self, organization_id: str) -> bool:
        return self._ok("DELETE", f"/organizations/{organization_id}")

    def members(self, organization_id: str) -> List[Dict[str, Any]]:
        return self._list("GET", f"/organizations/{organization_id}/members")

    def add_member(self, organization_id: str, *, email: Optional[str] = None, user_id: Optional[str] = None, role: Optional[str] = None) -> Any:
        return self._json("POST", f"/organizations/{organization_id}/members", json={k: v for k, v in {"id": user_id, "email": email, "role": role}.items() if v})

    def update_member(self, organization_id: str, *, email: Optional[str] = None, user_id: Optional[str] = None, role: Optional[str] = None) -> Any:
        return self._json("PATCH", f"/organizations/{organization_id}/members", json={k: v for k, v in {"id": user_id, "email": email, "role": role}.items() if v})

    def remove_member(self, organization_id: str, user_id: str) -> bool:
        return self._ok("DELETE", f"/organizations/{organization_id}/members/{user_id}")

    def projects(self, organization_id: str) -> List[Dict[str, Any]]:
        return self._list("GET", f"/organizations/{organization_id}/projects")

    def api_keys(self, organization_id: str) -> List[Dict[str, Any]]:
        return self._list("GET", f"/organizations/{organization_id}/api-keys")

    def llm_usage(self, organization_id: str) -> Any:
        return self._json("GET", f"/organizations/{organization_id}/llm-usage")

    def relayout_storage(self, organization_id: str) -> Any:
        """Rewrite the storage layout of the organization (maintenance)."""
        return self._json("POST", f"/organizations/{organization_id}/storage/relayout")

class AsyncOrganizations(AsyncResource):

    async def list(self) -> List[Dict[str, Any]]:
        return await self._list("GET", "/organizations")

    async def get(self, organization_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/organizations/{organization_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `description`, `storage`, `git`, `iceberg`."""
        return await self._json("POST", "/organizations", json=data)

    async def update(self, organization_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/organizations/{organization_id}", json=data)

    async def delete(self, organization_id: str) -> bool:
        return await self._ok("DELETE", f"/organizations/{organization_id}")

    async def members(self, organization_id: str) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/organizations/{organization_id}/members")

    async def add_member(self, organization_id: str, *, email: Optional[str] = None, user_id: Optional[str] = None, role: Optional[str] = None) -> Any:
        return await self._json("POST", f"/organizations/{organization_id}/members", json={k: v for k, v in {"id": user_id, "email": email, "role": role}.items() if v})

    async def update_member(self, organization_id: str, *, email: Optional[str] = None, user_id: Optional[str] = None, role: Optional[str] = None) -> Any:
        return await self._json("PATCH", f"/organizations/{organization_id}/members", json={k: v for k, v in {"id": user_id, "email": email, "role": role}.items() if v})

    async def remove_member(self, organization_id: str, user_id: str) -> bool:
        return await self._ok("DELETE", f"/organizations/{organization_id}/members/{user_id}")

    async def projects(self, organization_id: str) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/organizations/{organization_id}/projects")

    async def api_keys(self, organization_id: str) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/organizations/{organization_id}/api-keys")

    async def llm_usage(self, organization_id: str) -> Any:
        return await self._json("GET", f"/organizations/{organization_id}/llm-usage")

    async def relayout_storage(self, organization_id: str) -> Any:
        """Rewrite the storage layout of the organization (maintenance)."""
        return await self._json("POST", f"/organizations/{organization_id}/storage/relayout")
