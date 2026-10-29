"""`/api-keys` — the keys a project's automation authenticates with. The
secret is returned once, by `create`."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class ApiKeys(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/api-keys", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, api_key_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/api-keys/{api_key_id}")

    def create(self, *, name: str, project_id: str, scopes: Optional[List[str]] = None) -> Dict[str, Any]:
        return self._json("POST", "/api-keys", json={k: v for k, v in {"name": name, "project_id": project_id, "scopes": scopes}.items() if v is not None})

    def delete(self, api_key_id: str) -> bool:
        return self._ok("DELETE", f"/api-keys/{api_key_id}")

class AsyncApiKeys(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/api-keys", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, api_key_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/api-keys/{api_key_id}")

    async def create(self, *, name: str, project_id: str, scopes: Optional[List[str]] = None) -> Dict[str, Any]:
        return await self._json("POST", "/api-keys", json={k: v for k, v in {"name": name, "project_id": project_id, "scopes": scopes}.items() if v is not None})

    async def delete(self, api_key_id: str) -> bool:
        return await self._ok("DELETE", f"/api-keys/{api_key_id}")
