"""`/mediasets` — collections of media files (images, audio, video, documents)
of a given `media_type`, with the same file routes as a files dataset."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource
from gwenlake.files import _multipart


class Mediasets(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/mediasets", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, mediaset_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/mediasets/{mediaset_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `media_type` (see `media_types`)."""
        return self._json("POST", "/mediasets", json=data)

    def update(self, mediaset_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/mediasets/{mediaset_id}", json=data)

    def delete(self, mediaset_id: str) -> bool:
        return self._ok("DELETE", f"/mediasets/{mediaset_id}")

    def media_types(self) -> List[Dict[str, Any]]:
        return self._list("GET", "/mediasets/media-types")

    def summary(self, mediaset_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/mediasets/{mediaset_id}/summary")

    def empty(self, mediaset_id: str) -> bool:
        return self._ok("POST", f"/mediasets/{mediaset_id}/empty")

    def list_files(self, mediaset_id: str, *, path: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/mediasets/{mediaset_id}/files", params={"path": path})

    def download(self, mediaset_id: str, filepath: str) -> bytes:
        return self._bytes("GET", f"/mediasets/{mediaset_id}/files/{filepath}", accept="*/*")

    def presigned_url(self, mediaset_id: str, filepath: str, *, expires_in: Optional[int] = None) -> Any:
        return self._json("GET", f"/mediasets/{mediaset_id}/files/{filepath}/presigned-url", params={"expires_in": expires_in})

    def delete_file(self, mediaset_id: str, filepath: str) -> bool:
        return self._ok("DELETE", f"/mediasets/{mediaset_id}/files/{filepath}")

    def upload(self, mediaset_id: str, file: Any, *, path: Optional[str] = None, filename: Optional[str] = None) -> Any:
        """Upload a local path or raw bytes (`filename` required for bytes), under `path`."""
        return self._json("POST", f"/mediasets/{mediaset_id}/files" + (f"/{path}" if path else ""), files=_multipart(file, filename), accept="application/json")

class AsyncMediasets(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/mediasets", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, mediaset_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/mediasets/{mediaset_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `media_type` (see `media_types`)."""
        return await self._json("POST", "/mediasets", json=data)

    async def update(self, mediaset_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/mediasets/{mediaset_id}", json=data)

    async def delete(self, mediaset_id: str) -> bool:
        return await self._ok("DELETE", f"/mediasets/{mediaset_id}")

    async def media_types(self) -> List[Dict[str, Any]]:
        return await self._list("GET", "/mediasets/media-types")

    async def summary(self, mediaset_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/mediasets/{mediaset_id}/summary")

    async def empty(self, mediaset_id: str) -> bool:
        return await self._ok("POST", f"/mediasets/{mediaset_id}/empty")

    async def list_files(self, mediaset_id: str, *, path: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/mediasets/{mediaset_id}/files", params={"path": path})

    async def download(self, mediaset_id: str, filepath: str) -> bytes:
        return await self._bytes("GET", f"/mediasets/{mediaset_id}/files/{filepath}", accept="*/*")

    async def presigned_url(self, mediaset_id: str, filepath: str, *, expires_in: Optional[int] = None) -> Any:
        return await self._json("GET", f"/mediasets/{mediaset_id}/files/{filepath}/presigned-url", params={"expires_in": expires_in})

    async def delete_file(self, mediaset_id: str, filepath: str) -> bool:
        return await self._ok("DELETE", f"/mediasets/{mediaset_id}/files/{filepath}")

    async def upload(self, mediaset_id: str, file: Any, *, path: Optional[str] = None, filename: Optional[str] = None) -> Any:
        """Upload a local path or raw bytes (`filename` required for bytes), under `path`."""
        return await self._json("POST", f"/mediasets/{mediaset_id}/files" + (f"/{path}" if path else ""), files=_multipart(file, filename), accept="application/json")
