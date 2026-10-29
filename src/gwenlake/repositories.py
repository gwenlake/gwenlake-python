"""`/repositories` and `/git` — the code of a project.

A repository resource points at a git remote (`configuration.url`); the
platform clones it to run its transforms and **scans** it for the producer
declarations that make the lineage (`scan_lineage`, an asynchronous task:
pass `wait=True` to get its result, `transforms_found`, `edges_created`,
`warnings`). The `/git` routes read and write the repository through the
platform: `branches`, `tree`, `file`, `commit`, `create_branch`,
`delete_branch`, and `import_dataset` which commits a dataset's files into it.
"""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource
from gwenlake.builds import AsyncBuilds, Builds


class Repositories(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/repositories", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, repository_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/repositories/{repository_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `url` or `configuration` ({type: git, url, default_branch})."""
        return self._json("POST", "/repositories", json=data)

    def update(self, repository_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/repositories/{repository_id}", json=data)

    def delete(self, repository_id: str) -> bool:
        return self._ok("DELETE", f"/repositories/{repository_id}")

    def rotate_credentials(self, repository_id: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PUT", f"/repositories/{repository_id}/credentials", json={"credentials": credentials})

    def scan_lineage(self, repository_id: str, *, ref: Optional[str] = None, wait: bool = False,
                     timeout: Optional[float] = 600) -> Dict[str, Any]:
        """Scan the code for producer declarations and sync the transforms and
        the lineage. Answers `{repository_id, task_id}`; with `wait`, the task's
        final state, its `result` holding the scan's counts and warnings."""
        task = self._json("POST", f"/orchestration/repositories/{repository_id}/scan-lineage", params={"ref": ref})
        if not wait:
            return task
        return Builds(self._client).wait_task(task["task_id"], timeout=timeout)

    # -- git ---------------------------------------------------------------

    def branches(self, repository_id: str) -> Any:
        return self._json("GET", f"/git/{repository_id}/branches")

    def tree(self, repository_id: str, *, ref: Optional[str] = None, path: Optional[str] = None) -> Any:
        return self._json("GET", f"/git/{repository_id}/tree", params={"ref": ref, "path": path})

    def file(self, repository_id: str, path: str, *, ref: Optional[str] = None) -> Any:
        return self._json("GET", f"/git/{repository_id}/file", params={"path": path, "ref": ref})

    def commit(self, repository_id: str, *, ref: str, message: str, changes: List[Dict[str, Any]],
               author: Optional[Dict[str, str]] = None) -> Any:
        """Commit `changes` (the catalog's change entries: path, content or delete) on `ref`."""
        body: Dict[str, Any] = {"ref": ref, "message": message, "changes": changes}
        if author:
            body["author"] = author
        return self._json("POST", f"/git/{repository_id}/commit", json=body)

    def create_branch(self, repository_id: str, name: str, *, from_ref: str) -> Any:
        return self._json("POST", f"/git/{repository_id}/branches", json={"name": name, "from_ref": from_ref})

    def delete_branch(self, repository_id: str, name: str) -> bool:
        return self._ok("DELETE", f"/git/{repository_id}/branches/{name}")

    def import_dataset(self, repository_id: str, *, dataset_id: str, path: str, ref: Optional[str] = None,
                       name: Optional[str] = None) -> Any:
        """Commit the files of `dataset_id` under `path` of the repository."""
        return self._json("POST", f"/git/{repository_id}/import",
                          json={k: v for k, v in {"dataset_id": dataset_id, "path": path, "ref": ref, "name": name}.items() if v is not None})


class AsyncRepositories(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/repositories", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, repository_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/repositories/{repository_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("POST", "/repositories", json=data)

    async def update(self, repository_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/repositories/{repository_id}", json=data)

    async def delete(self, repository_id: str) -> bool:
        return await self._ok("DELETE", f"/repositories/{repository_id}")

    async def rotate_credentials(self, repository_id: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PUT", f"/repositories/{repository_id}/credentials", json={"credentials": credentials})

    async def scan_lineage(self, repository_id: str, *, ref: Optional[str] = None, wait: bool = False,
                           timeout: Optional[float] = 600) -> Dict[str, Any]:
        task = await self._json("POST", f"/orchestration/repositories/{repository_id}/scan-lineage", params={"ref": ref})
        if not wait:
            return task
        return await AsyncBuilds(self._client).wait_task(task["task_id"], timeout=timeout)

    async def branches(self, repository_id: str) -> Any:
        return await self._json("GET", f"/git/{repository_id}/branches")

    async def tree(self, repository_id: str, *, ref: Optional[str] = None, path: Optional[str] = None) -> Any:
        return await self._json("GET", f"/git/{repository_id}/tree", params={"ref": ref, "path": path})

    async def file(self, repository_id: str, path: str, *, ref: Optional[str] = None) -> Any:
        return await self._json("GET", f"/git/{repository_id}/file", params={"path": path, "ref": ref})

    async def commit(self, repository_id: str, *, ref: str, message: str, changes: List[Dict[str, Any]],
                     author: Optional[Dict[str, str]] = None) -> Any:
        body: Dict[str, Any] = {"ref": ref, "message": message, "changes": changes}
        if author:
            body["author"] = author
        return await self._json("POST", f"/git/{repository_id}/commit", json=body)

    async def create_branch(self, repository_id: str, name: str, *, from_ref: str) -> Any:
        return await self._json("POST", f"/git/{repository_id}/branches", json={"name": name, "from_ref": from_ref})

    async def delete_branch(self, repository_id: str, name: str) -> bool:
        return await self._ok("DELETE", f"/git/{repository_id}/branches/{name}")

    async def import_dataset(self, repository_id: str, *, dataset_id: str, path: str, ref: Optional[str] = None,
                             name: Optional[str] = None) -> Any:
        return await self._json("POST", f"/git/{repository_id}/import",
                                json={k: v for k, v in {"dataset_id": dataset_id, "path": path, "ref": ref, "name": name}.items() if v is not None})
