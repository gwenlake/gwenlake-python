"""`/transforms` — the catalog's **producers**: the resource that says how a
dataset (or a model) is made. Four kinds: `sql` (a stored sql-query),
`python` and `train` (a function of a repository), `function` (a ready-made
transform of the platform, see `functions`). The lineage graph is derived
from their `inputs` and `output`; a repository scan creates and updates them,
this resource reads and adjusts them (a `config.parameters` block, a name).

Not to be confused with :mod:`gwenlake.transforms`, the decorators a
repository's code is written with.
"""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Transforms(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None,
             output: Optional[str] = None) -> List[Dict[str, Any]]:
        """`output` narrows to the transforms producing that dataset or model id."""
        return self._list("GET", "/transforms", params={"project_id": project_id, "organization_id": organization_id, "output": output})

    def get(self, transform_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/transforms/{transform_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `type` (sql | python | train | function),
        `output` (dataset or model id), `inputs` (ids), `config`."""
        return self._json("POST", "/transforms", json=data)

    def update(self, transform_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Partial update. `config` replaces the whole block: use `set_parameters`
        to change the settings only."""
        return self._json("PATCH", f"/transforms/{transform_id}", json=data)

    def set_parameters(self, transform_id: str, parameters: Dict[str, Any], *, merge: bool = True) -> Dict[str, Any]:
        """Set `config.parameters` (what a build receives as `TRANSFORM_PARAMETERS`),
        keeping the rest of the config; `merge=False` replaces the existing parameters."""
        config = dict(self.get(transform_id).get("config") or {})
        config["parameters"] = {**(config.get("parameters") or {}), **parameters} if merge else dict(parameters)
        return self.update(transform_id, {"config": config})

    def delete(self, transform_id: str) -> bool:
        return self._ok("DELETE", f"/transforms/{transform_id}")

    def restore(self, transform_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/transforms/{transform_id}/restore")

    def execute(self, transform_id: str, *, branch: Optional[str] = None) -> Any:
        """Build the transform's output now (on a data `branch` when given)."""
        return self._json("POST", f"/transforms/{transform_id}/execute", params={"branch": branch})

    def functions(self) -> List[Dict[str, Any]]:
        """The ready-made transform functions of the platform and their parameters."""
        return self._list("GET", "/transforms/functions")


class AsyncTransforms(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None,
                   output: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/transforms", params={"project_id": project_id, "organization_id": organization_id, "output": output})

    async def get(self, transform_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/transforms/{transform_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("POST", "/transforms", json=data)

    async def update(self, transform_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/transforms/{transform_id}", json=data)

    async def set_parameters(self, transform_id: str, parameters: Dict[str, Any], *, merge: bool = True) -> Dict[str, Any]:
        config = dict((await self.get(transform_id)).get("config") or {})
        config["parameters"] = {**(config.get("parameters") or {}), **parameters} if merge else dict(parameters)
        return await self.update(transform_id, {"config": config})

    async def delete(self, transform_id: str) -> bool:
        return await self._ok("DELETE", f"/transforms/{transform_id}")

    async def restore(self, transform_id: str) -> Dict[str, Any]:
        return await self._json("POST", f"/transforms/{transform_id}/restore")

    async def execute(self, transform_id: str, *, branch: Optional[str] = None) -> Any:
        return await self._json("POST", f"/transforms/{transform_id}/execute", params={"branch": branch})

    async def functions(self) -> List[Dict[str, Any]]:
        return await self._list("GET", "/transforms/functions")
