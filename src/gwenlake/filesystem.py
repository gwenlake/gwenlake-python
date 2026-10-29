"""`/filesystem` — the tree every resource lives in: projects hold folders and
resources; `search` finds a resource by name across it; `move`, `rename`,
`restore` and `logo` act on any resource by id. (Projects themselves are
`client.projects`.)"""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource
from gwenlake.files import _multipart


class Filesystem(Resource):

    def search(self, q: str, *, project_id: Optional[str] = None, organization_id: Optional[str] = None, type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/filesystem/search", params={"q": q, "project_id": project_id, "organization_id": organization_id, "type": type})

    def resources(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None, type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Every resource, optionally of one `type` (dataset, repository, schedule...)."""
        return self._list("GET", "/filesystem/resources", params={"project_id": project_id, "organization_id": organization_id, "type": type})

    def resource(self, resource_id: str) -> Dict[str, Any]:
        """Any resource by id, whatever its type."""
        return self._json("GET", f"/filesystem/resources/{resource_id}")

    def move(self, resource_id: str, parent_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/filesystem/resources/{resource_id}/move", json={"parent_id": parent_id})

    def rename(self, resource_id: str, name: str, *, slug: Optional[str] = None) -> Dict[str, Any]:
        return self._json("POST", f"/filesystem/resources/{resource_id}/rename", json={k: v for k, v in {"name": name, "slug": slug}.items() if v})

    def restore(self, resource_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/filesystem/resources/{resource_id}/restore")

    def upload_logo(self, resource_id: str, file: Any, *, filename: Optional[str] = None) -> Any:
        return self._json("POST", f"/filesystem/resources/{resource_id}/logo", files=_multipart(file, filename))

    def folder(self, folder_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/filesystem/folders/{folder_id}")

    def children(self, folder_id: str, *, type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/filesystem/folders/{folder_id}/children", params={"type": type})

    def create_folder(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id` or `parent_id`."""
        return self._json("POST", "/filesystem/folders", json=data)

    def update_folder(self, folder_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/filesystem/folders/{folder_id}", json=data)

    def delete_folder(self, folder_id: str) -> bool:
        return self._ok("DELETE", f"/filesystem/folders/{folder_id}")

class AsyncFilesystem(AsyncResource):

    async def search(self, q: str, *, project_id: Optional[str] = None, organization_id: Optional[str] = None, type: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/filesystem/search", params={"q": q, "project_id": project_id, "organization_id": organization_id, "type": type})

    async def resources(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None, type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Every resource, optionally of one `type` (dataset, repository, schedule...)."""
        return await self._list("GET", "/filesystem/resources", params={"project_id": project_id, "organization_id": organization_id, "type": type})

    async def resource(self, resource_id: str) -> Dict[str, Any]:
        """Any resource by id, whatever its type."""
        return await self._json("GET", f"/filesystem/resources/{resource_id}")

    async def move(self, resource_id: str, parent_id: str) -> Dict[str, Any]:
        return await self._json("POST", f"/filesystem/resources/{resource_id}/move", json={"parent_id": parent_id})

    async def rename(self, resource_id: str, name: str, *, slug: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("POST", f"/filesystem/resources/{resource_id}/rename", json={k: v for k, v in {"name": name, "slug": slug}.items() if v})

    async def restore(self, resource_id: str) -> Dict[str, Any]:
        return await self._json("POST", f"/filesystem/resources/{resource_id}/restore")

    async def upload_logo(self, resource_id: str, file: Any, *, filename: Optional[str] = None) -> Any:
        return await self._json("POST", f"/filesystem/resources/{resource_id}/logo", files=_multipart(file, filename))

    async def folder(self, folder_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/filesystem/folders/{folder_id}")

    async def children(self, folder_id: str, *, type: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/filesystem/folders/{folder_id}/children", params={"type": type})

    async def create_folder(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id` or `parent_id`."""
        return await self._json("POST", "/filesystem/folders", json=data)

    async def update_folder(self, folder_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/filesystem/folders/{folder_id}", json=data)

    async def delete_folder(self, folder_id: str) -> bool:
        return await self._ok("DELETE", f"/filesystem/folders/{folder_id}")
