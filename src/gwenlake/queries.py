"""`/sql/queries` — the **stored** SQL: a versioned sql-query resource, the
text behind every `sql` transform. (`statements` is the ad hoc form, run
live and stored nowhere.)
"""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Queries(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/sql/queries", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, query_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return self._json("GET", f"/sql/queries/{query_id}", params={"branch": branch})

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `sql` (the text), `description`..."""
        return self._json("POST", "/sql/queries", json=data)

    def update(self, query_id: str, data: Dict[str, Any], *, branch: Optional[str] = None) -> Dict[str, Any]:
        return self._json("PATCH", f"/sql/queries/{query_id}", json=data, params={"branch": branch})

    def delete(self, query_id: str) -> bool:
        return self._ok("DELETE", f"/sql/queries/{query_id}")

    def restore(self, query_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/sql/queries/{query_id}/restore")

    def execute(self, query_id: str, *, branch: Optional[str] = None) -> Any:
        """Build the dataset this query produces (on a data `branch` when given)."""
        return self._json("POST", f"/sql/queries/{query_id}/execute", params={"branch": branch})

    def versions(self, query_id: str, *, limit: Optional[int] = None, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/sql/queries/{query_id}/versions", params={"limit": limit, "branch": branch})

    def version(self, query_id: str, version_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return self._json("GET", f"/sql/queries/{query_id}/versions/{version_id}", params={"branch": branch})


class AsyncQueries(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/sql/queries", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, query_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("GET", f"/sql/queries/{query_id}", params={"branch": branch})

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("POST", "/sql/queries", json=data)

    async def update(self, query_id: str, data: Dict[str, Any], *, branch: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("PATCH", f"/sql/queries/{query_id}", json=data, params={"branch": branch})

    async def delete(self, query_id: str) -> bool:
        return await self._ok("DELETE", f"/sql/queries/{query_id}")

    async def restore(self, query_id: str) -> Dict[str, Any]:
        return await self._json("POST", f"/sql/queries/{query_id}/restore")

    async def execute(self, query_id: str, *, branch: Optional[str] = None) -> Any:
        return await self._json("POST", f"/sql/queries/{query_id}/execute", params={"branch": branch})

    async def versions(self, query_id: str, *, limit: Optional[int] = None, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/sql/queries/{query_id}/versions", params={"limit": limit, "branch": branch})

    async def version(self, query_id: str, version_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("GET", f"/sql/queries/{query_id}/versions/{version_id}", params={"branch": branch})
