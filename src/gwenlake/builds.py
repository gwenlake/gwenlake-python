"""`/orchestration/builds` and `/orchestration/tasks` — running the workflow.

A **build** materializes a dataset (or a model): `run` resolves the target's
stale upstream chain into one build per node, chained in order, and answers
the whole batch; `wait` follows a build to its end. A **task** is the other
asynchronous job the catalog runs, a repository scan for instance
(`repositories.scan_lineage`): `task` reads its state, `wait_task` follows it.

A build goes `PENDING` → `RUNNING` → `SUCCESS` | `FAILED` | `CANCELLED`; a
function with several outputs runs at most once at a time, so a second build
of it is refused (409) while one is live.
"""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, JobFailed, Resource, poll, poll_async

FAILED_STATES = frozenset({"FAILED", "CANCELLED", "FAILURE", "REVOKED", "failed", "cancelled"})


def _check(job: Dict[str, Any], what: str, raise_on_failure: bool) -> Dict[str, Any]:
    status = str(job.get("status", ""))
    if raise_on_failure and status in FAILED_STATES:
        detail = job.get("error_message") or job.get("error") or ""
        raise JobFailed(f"{what} {job.get('id') or job.get('task_id')} {status}: {detail}".strip(), job)
    return job


class Builds(Resource):

    def run(self, target_id: str, *, target_only: bool = False, branch: Optional[str] = None,
            source_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Trigger a build of `target_id` (a dataset or model id). Answers the
        batch: `group_id`, `target_id` and `builds` in topological order, the
        last one being the target's. `target_only` skips the upstream chain;
        `branch` writes every output on that Iceberg data branch."""
        body: Dict[str, Any] = {"target_id": target_id, "target_only": target_only}
        if branch:
            body["branch"] = branch
        if source_id:
            body["source_id"] = source_id
        if context:
            body["context"] = context
        return self._json("POST", "/orchestration/builds", json=body)

    def list(self, *, target_id: Optional[str] = None, status: Optional[str] = None,
             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/orchestration/builds", params={"target_id": target_id, "status": status, "limit": limit})

    def get(self, build_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/orchestration/builds/{build_id}")

    def logs(self, build_id: str, *, tail: Optional[int] = None) -> Dict[str, Any]:
        """The build's log lines (`logs`, one string) with its status."""
        return self._json("GET", f"/orchestration/builds/{build_id}/logs", params={"tail": tail})

    def cancel(self, build_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/orchestration/builds/{build_id}/cancel")

    def wait(self, build_id: str, *, timeout: Optional[float] = 3600, interval: float = 5.0,
             raise_on_failure: bool = True) -> Dict[str, Any]:
        """Poll the build until it settles; `JobFailed` on FAILED/CANCELLED
        unless `raise_on_failure` is false."""
        job = poll(lambda: self.get(build_id), status_of=lambda b: str(b.get("status", "")),
                   timeout=timeout, interval=interval, what=f"build {build_id}")
        return _check(job, "build", raise_on_failure)

    def run_and_wait(self, target_id: str, *, timeout: Optional[float] = 3600, interval: float = 5.0,
                     **run_kwargs: Any) -> Dict[str, Any]:
        """`run` then `wait` on the target's build; answers the batch with
        every build refreshed."""
        batch = self.run(target_id, **run_kwargs)
        self.wait(batch["builds"][-1]["id"], timeout=timeout, interval=interval)
        batch["builds"] = [self.get(b["id"]) for b in batch["builds"]]
        return batch

    def task(self, task_id: str) -> Dict[str, Any]:
        """The state of an asynchronous task (`status`, `ready`, `result`, `error`)."""
        return self._json("GET", f"/orchestration/tasks/{task_id}")

    def wait_task(self, task_id: str, *, timeout: Optional[float] = 600, interval: float = 3.0,
                  raise_on_failure: bool = True) -> Dict[str, Any]:
        job = poll(lambda: self.task(task_id), status_of=lambda t: str(t.get("status", "")),
                   timeout=timeout, interval=interval, what=f"task {task_id}")
        return _check(job, "task", raise_on_failure)


class AsyncBuilds(AsyncResource):

    async def run(self, target_id: str, *, target_only: bool = False, branch: Optional[str] = None,
                  source_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"target_id": target_id, "target_only": target_only}
        if branch:
            body["branch"] = branch
        if source_id:
            body["source_id"] = source_id
        if context:
            body["context"] = context
        return await self._json("POST", "/orchestration/builds", json=body)

    async def list(self, *, target_id: Optional[str] = None, status: Optional[str] = None,
                   limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/orchestration/builds", params={"target_id": target_id, "status": status, "limit": limit})

    async def get(self, build_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/orchestration/builds/{build_id}")

    async def logs(self, build_id: str, *, tail: Optional[int] = None) -> Dict[str, Any]:
        return await self._json("GET", f"/orchestration/builds/{build_id}/logs", params={"tail": tail})

    async def cancel(self, build_id: str) -> Dict[str, Any]:
        return await self._json("POST", f"/orchestration/builds/{build_id}/cancel")

    async def wait(self, build_id: str, *, timeout: Optional[float] = 3600, interval: float = 5.0,
                   raise_on_failure: bool = True) -> Dict[str, Any]:
        async def fetch():
            return await self.get(build_id)
        job = await poll_async(fetch, status_of=lambda b: str(b.get("status", "")),
                               timeout=timeout, interval=interval, what=f"build {build_id}")
        return _check(job, "build", raise_on_failure)

    async def run_and_wait(self, target_id: str, *, timeout: Optional[float] = 3600, interval: float = 5.0,
                           **run_kwargs: Any) -> Dict[str, Any]:
        batch = await self.run(target_id, **run_kwargs)
        await self.wait(batch["builds"][-1]["id"], timeout=timeout, interval=interval)
        batch["builds"] = [await self.get(b["id"]) for b in batch["builds"]]
        return batch

    async def task(self, task_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/orchestration/tasks/{task_id}")

    async def wait_task(self, task_id: str, *, timeout: Optional[float] = 600, interval: float = 3.0,
                        raise_on_failure: bool = True) -> Dict[str, Any]:
        async def fetch():
            return await self.task(task_id)
        job = await poll_async(fetch, status_of=lambda t: str(t.get("status", "")),
                               timeout=timeout, interval=interval, what=f"task {task_id}")
        return _check(job, "task", raise_on_failure)
