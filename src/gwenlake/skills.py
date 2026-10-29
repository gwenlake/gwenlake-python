"""`/skills` — reusable instruction sets an agent can load, versioned."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Skills(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/skills", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, skill_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/skills/{skill_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `instructions`, `license`, `compatibility`."""
        return self._json("POST", "/skills", json=data)

    def update(self, skill_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/skills/{skill_id}", json=data)

    def delete(self, skill_id: str) -> bool:
        return self._ok("DELETE", f"/skills/{skill_id}")

    def restore(self, skill_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/skills/{skill_id}/restore")

    def versions(self, skill_id: str, *, limit: Optional[int] = None, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/skills/{skill_id}/versions", params={"limit": limit, "branch": branch})

    def version(self, skill_id: str, version_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return self._json("GET", f"/skills/{skill_id}/versions/{version_id}", params={"branch": branch})

class AsyncSkills(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/skills", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, skill_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/skills/{skill_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `instructions`, `license`, `compatibility`."""
        return await self._json("POST", "/skills", json=data)

    async def update(self, skill_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/skills/{skill_id}", json=data)

    async def delete(self, skill_id: str) -> bool:
        return await self._ok("DELETE", f"/skills/{skill_id}")

    async def restore(self, skill_id: str) -> Dict[str, Any]:
        return await self._json("POST", f"/skills/{skill_id}/restore")

    async def versions(self, skill_id: str, *, limit: Optional[int] = None, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/skills/{skill_id}/versions", params={"limit": limit, "branch": branch})

    async def version(self, skill_id: str, version_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("GET", f"/skills/{skill_id}/versions/{version_id}", params={"branch": branch})
