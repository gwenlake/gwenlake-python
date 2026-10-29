"""`/ontologies` — object types, their instances and the links between them."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Ontologies(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/ontologies", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, ontology_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/ontologies/{ontology_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `api_name`, `project_id`, `version`, `base_uri`, `object_types`, `link_types`."""
        return self._json("POST", "/ontologies", json=data)

    def update(self, ontology_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/ontologies/{ontology_id}", json=data)

    def delete(self, ontology_id: str) -> bool:
        return self._ok("DELETE", f"/ontologies/{ontology_id}")

    def objects(self, ontology_id: str, object_type: str, *, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/ontologies/{ontology_id}/objects/{object_type}", params={"limit": limit, "offset": offset})

    def object(self, ontology_id: str, object_type: str, primary_key: str) -> Dict[str, Any]:
        return self._json("GET", f"/ontologies/{ontology_id}/objects/{object_type}/{primary_key}")

    def linked_objects(self, ontology_id: str, object_type: str, primary_key: str, link_type: str, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/ontologies/{ontology_id}/objects/{object_type}/{primary_key}/links/{link_type}", params={"limit": limit})

    def links(self, ontology_id: str, link_type: str, *, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/ontologies/{ontology_id}/links/{link_type}", params={"limit": limit, "offset": offset})

class AsyncOntologies(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/ontologies", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, ontology_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/ontologies/{ontology_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `api_name`, `project_id`, `version`, `base_uri`, `object_types`, `link_types`."""
        return await self._json("POST", "/ontologies", json=data)

    async def update(self, ontology_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/ontologies/{ontology_id}", json=data)

    async def delete(self, ontology_id: str) -> bool:
        return await self._ok("DELETE", f"/ontologies/{ontology_id}")

    async def objects(self, ontology_id: str, object_type: str, *, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/ontologies/{ontology_id}/objects/{object_type}", params={"limit": limit, "offset": offset})

    async def object(self, ontology_id: str, object_type: str, primary_key: str) -> Dict[str, Any]:
        return await self._json("GET", f"/ontologies/{ontology_id}/objects/{object_type}/{primary_key}")

    async def linked_objects(self, ontology_id: str, object_type: str, primary_key: str, link_type: str, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/ontologies/{ontology_id}/objects/{object_type}/{primary_key}/links/{link_type}", params={"limit": limit})

    async def links(self, ontology_id: str, link_type: str, *, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/ontologies/{ontology_id}/links/{link_type}", params={"limit": limit, "offset": offset})
