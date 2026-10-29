"""`/mlmodels` — the catalog's **ML models**: a model card (framework, task,
version, parameters, metrics) whose artifacts live in a repository, trained
by a `train` transform and loaded by a `python` one. Not the inference
models of `client.models`."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class MLModels(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/mlmodels", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, model_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/mlmodels/{model_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `repository_id`, `path`, `framework`, `task`, `version`, `parameters`, `metrics`."""
        return self._json("POST", "/mlmodels", json=data)

    def update(self, model_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/mlmodels/{model_id}", json=data)

    def delete(self, model_id: str) -> bool:
        return self._ok("DELETE", f"/mlmodels/{model_id}")

    def restore(self, model_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/mlmodels/{model_id}/restore")

    def execute(self, model_id: str, *, branch: Optional[str] = None) -> Any:
        """Run the training transform that produces the model."""
        return self._json("POST", f"/mlmodels/{model_id}/execute", params={"branch": branch})

    def files(self, model_id: str, *, revision: Optional[str] = None) -> List[Dict[str, Any]]:
        """The artifact files of a revision (the pinned one by default)."""
        return self._list("GET", f"/mlmodels/{model_id}/files", params={"revision": revision})

    def resolve(self, model_id: str, revision: str, filepath: str) -> bytes:
        """The bytes of one artifact file at a revision."""
        return self._bytes("GET", f"/mlmodels/{model_id}/resolve/{revision}/{filepath}", accept="*/*")

    def missing_artifacts(self, model_id: str, oids: List[str]) -> Any:
        """Which of these LFS object ids the platform does not hold yet."""
        return self._json("POST", f"/mlmodels/{model_id}/artifacts/missing", json={"oids": oids})

class AsyncMLModels(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/mlmodels", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, model_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/mlmodels/{model_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `repository_id`, `path`, `framework`, `task`, `version`, `parameters`, `metrics`."""
        return await self._json("POST", "/mlmodels", json=data)

    async def update(self, model_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/mlmodels/{model_id}", json=data)

    async def delete(self, model_id: str) -> bool:
        return await self._ok("DELETE", f"/mlmodels/{model_id}")

    async def restore(self, model_id: str) -> Dict[str, Any]:
        return await self._json("POST", f"/mlmodels/{model_id}/restore")

    async def execute(self, model_id: str, *, branch: Optional[str] = None) -> Any:
        """Run the training transform that produces the model."""
        return await self._json("POST", f"/mlmodels/{model_id}/execute", params={"branch": branch})

    async def files(self, model_id: str, *, revision: Optional[str] = None) -> List[Dict[str, Any]]:
        """The artifact files of a revision (the pinned one by default)."""
        return await self._list("GET", f"/mlmodels/{model_id}/files", params={"revision": revision})

    async def resolve(self, model_id: str, revision: str, filepath: str) -> bytes:
        """The bytes of one artifact file at a revision."""
        return await self._bytes("GET", f"/mlmodels/{model_id}/resolve/{revision}/{filepath}", accept="*/*")

    async def missing_artifacts(self, model_id: str, oids: List[str]) -> Any:
        """Which of these LFS object ids the platform does not hold yet."""
        return await self._json("POST", f"/mlmodels/{model_id}/artifacts/missing", json={"oids": oids})
