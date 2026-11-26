"""`/ontologies` — object types, their instances and the links between them."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


def _query_body(filters, properties, order_by, limit, offset, count) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if filters:
        body["filters"] = filters
    if properties is not None:
        body["properties"] = properties
    if order_by:
        body["order_by"] = order_by
    if limit is not None:
        body["limit"] = limit
    if offset is not None:
        body["offset"] = offset
    if count:
        body["count"] = True
    return body


def _decision_body(reason: Optional[str]) -> Optional[Dict[str, Any]]:
    return {"reason": reason} if reason is not None else None


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

    def linked_objects(self, ontology_id: str, object_type: str, primary_key: str, link_type: str, *, limit: Optional[int] = None, offset: Optional[int] = None, direction: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/ontologies/{ontology_id}/objects/{object_type}/{primary_key}/links/{link_type}", params={"limit": limit, "offset": offset, "direction": direction})

    def links(self, ontology_id: str, link_type: str, *, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/ontologies/{ontology_id}/links/{link_type}", params={"limit": limit, "offset": offset})

    def query(self, ontology_id: str, object_type: str, *, filters: Optional[List[Dict[str, Any]]] = None, properties: Optional[List[str]] = None, order_by: Optional[List[Dict[str, Any]]] = None, limit: Optional[int] = None, offset: Optional[int] = None, count: bool = False) -> Dict[str, Any]:
        return self._json("POST", f"/ontologies/{ontology_id}/objects/{object_type}/query", json=_query_body(filters, properties, order_by, limit, offset, count))

    def validate_action(self, ontology_id: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("POST", f"/ontologies/{ontology_id}/actions/{action}/validate", json={"parameters": parameters})

    def apply_action(self, ontology_id: str, action: str, parameters: Dict[str, Any], *, propose: bool = False) -> Dict[str, Any]:
        return self._json("POST", f"/ontologies/{ontology_id}/actions/{action}/apply", json={"parameters": parameters, "propose": propose})

    def action_runs(self, ontology_id: str, *, status: Optional[str] = None, action: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        return self._json("GET", f"/ontologies/{ontology_id}/action-runs", params={"status": status, "action": action, "limit": limit, "offset": offset})

    def action_run(self, ontology_id: str, run_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/ontologies/{ontology_id}/action-runs/{run_id}")

    def approve_action_run(self, ontology_id: str, run_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
        return self._json("POST", f"/ontologies/{ontology_id}/action-runs/{run_id}/approve", json=_decision_body(reason))

    def reject_action_run(self, ontology_id: str, run_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
        return self._json("POST", f"/ontologies/{ontology_id}/action-runs/{run_id}/reject", json=_decision_body(reason))

    def versions(self, ontology_id: str, *, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/ontologies/{ontology_id}/versions", params={"limit": limit, "offset": offset})

    def branches(self, ontology_id: str) -> List[Dict[str, Any]]:
        return self._list("GET", f"/ontologies/{ontology_id}/branches")


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

    async def linked_objects(self, ontology_id: str, object_type: str, primary_key: str, link_type: str, *, limit: Optional[int] = None, offset: Optional[int] = None, direction: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/ontologies/{ontology_id}/objects/{object_type}/{primary_key}/links/{link_type}", params={"limit": limit, "offset": offset, "direction": direction})

    async def links(self, ontology_id: str, link_type: str, *, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/ontologies/{ontology_id}/links/{link_type}", params={"limit": limit, "offset": offset})

    async def query(self, ontology_id: str, object_type: str, *, filters: Optional[List[Dict[str, Any]]] = None, properties: Optional[List[str]] = None, order_by: Optional[List[Dict[str, Any]]] = None, limit: Optional[int] = None, offset: Optional[int] = None, count: bool = False) -> Dict[str, Any]:
        return await self._json("POST", f"/ontologies/{ontology_id}/objects/{object_type}/query", json=_query_body(filters, properties, order_by, limit, offset, count))

    async def validate_action(self, ontology_id: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("POST", f"/ontologies/{ontology_id}/actions/{action}/validate", json={"parameters": parameters})

    async def apply_action(self, ontology_id: str, action: str, parameters: Dict[str, Any], *, propose: bool = False) -> Dict[str, Any]:
        return await self._json("POST", f"/ontologies/{ontology_id}/actions/{action}/apply", json={"parameters": parameters, "propose": propose})

    async def action_runs(self, ontology_id: str, *, status: Optional[str] = None, action: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        return await self._json("GET", f"/ontologies/{ontology_id}/action-runs", params={"status": status, "action": action, "limit": limit, "offset": offset})

    async def action_run(self, ontology_id: str, run_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/ontologies/{ontology_id}/action-runs/{run_id}")

    async def approve_action_run(self, ontology_id: str, run_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("POST", f"/ontologies/{ontology_id}/action-runs/{run_id}/approve", json=_decision_body(reason))

    async def reject_action_run(self, ontology_id: str, run_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("POST", f"/ontologies/{ontology_id}/action-runs/{run_id}/reject", json=_decision_body(reason))

    async def versions(self, ontology_id: str, *, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/ontologies/{ontology_id}/versions", params={"limit": limit, "offset": offset})

    async def branches(self, ontology_id: str) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/ontologies/{ontology_id}/branches")
