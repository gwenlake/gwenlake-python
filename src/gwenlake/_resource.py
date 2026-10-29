"""What every catalog resource module shares: one request helper per answer
shape, and the polling of an asynchronous server-side job.

A resource class holds the transport (`ApiClient` / `AsyncApiClient`) and
turns each API route into one method. The catalog answers a **list** route
with an envelope (``{"object": "list", "data": [...]}``), a **get/create/
update** route with the object itself, and a **delete** route with nothing
worth returning; `_list`, `_json` and `_ok` are those three shapes. `None`
query parameters are dropped so that an optional argument left unset sends
exactly the request the route expects by default.
"""

import time
from typing import Any, Callable, Dict, List, Optional

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions
from gwenlake.exceptions import GwenlakeException

JSON = "application/json"


def _clean(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {k: v for k, v in (params or {}).items() if v is not None}


def _options(method: str, url: str, *, params=None, json=None, headers=None, timeout=None,
             accept: str = JSON, files=None) -> RequestOptions:
    sent = {"Accept": accept}
    if json is not None:
        sent["Content-Type"] = JSON
    sent.update(headers or {})
    return RequestOptions(method=method, url=url, params=_clean(params), json_data=json, headers=sent,
                          timeout=timeout, files=files)


def _decode(response) -> Any:
    """The JSON of an answer; a page of HTML means the URL is not an API
    endpoint (an Atlas host serves it under /api/v1, an API host under /v1)."""
    if not response.content:
        return None
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type:
        raise GwenlakeException(
            f"{response.request.method} {response.request.url} answered {content_type or 'no content type'} "
            f"instead of JSON: not an API endpoint. An Atlas host serves the API under /api/v1, an API host "
            f"under /v1 (see `gwenlake config set-profile --base-url`)."
        )
    return response.json()


def _unwrap(body: Any) -> Any:
    """The rows of a list answer, whether the catalog wrapped them or not."""
    if isinstance(body, dict) and body.get("object") == "list":
        return body.get("data") or []
    if isinstance(body, dict) and "data" in body and isinstance(body["data"], list):
        return body["data"]
    return body


class Resource:
    """Synchronous base: subclasses call `_json`, `_list`, `_bytes` or `_ok`."""

    def __init__(self, client: ApiClient):
        self._client = client

    def _send(self, method: str, url: str, **kwargs: Any):
        response = self._client.send(_options(method, url, **kwargs))
        response.raise_for_status()
        return response

    def _json(self, method: str, url: str, **kwargs: Any) -> Any:
        return _decode(self._send(method, url, **kwargs))

    def _list(self, method: str, url: str, **kwargs: Any) -> List[Dict[str, Any]]:
        return _unwrap(self._json(method, url, **kwargs))

    def _bytes(self, method: str, url: str, **kwargs: Any) -> bytes:
        return self._send(method, url, **kwargs).content

    def _ok(self, method: str, url: str, **kwargs: Any) -> bool:
        self._send(method, url, **kwargs)
        return True


class AsyncResource:
    """Asynchronous twin of :class:`Resource`."""

    def __init__(self, client: AsyncApiClient):
        self._client = client

    async def _send(self, method: str, url: str, **kwargs: Any):
        response = await self._client.send(_options(method, url, **kwargs))
        response.raise_for_status()
        return response

    async def _json(self, method: str, url: str, **kwargs: Any) -> Any:
        return _decode(await self._send(method, url, **kwargs))

    async def _list(self, method: str, url: str, **kwargs: Any) -> List[Dict[str, Any]]:
        return _unwrap(await self._json(method, url, **kwargs))

    async def _bytes(self, method: str, url: str, **kwargs: Any) -> bytes:
        return (await self._send(method, url, **kwargs)).content

    async def _ok(self, method: str, url: str, **kwargs: Any) -> bool:
        await self._send(method, url, **kwargs)
        return True


# ---------------------------------------------------------------------------
# Server-side jobs (builds, scans): poll until they settle
# ---------------------------------------------------------------------------

#: States in which a build or a task is still going.
LIVE_STATES = frozenset({"PENDING", "RUNNING", "STARTED", "QUEUED", "RETRY", "dispatched", "running", "pending"})


class JobFailed(GwenlakeException):
    """A build or a task settled in a failure state. `job` is its last state."""

    def __init__(self, message: str, job: Dict[str, Any]):
        super().__init__(message)
        self.job = job


def poll(fetch: Callable[[], Dict[str, Any]], *, status_of: Callable[[Dict[str, Any]], str],
         timeout: Optional[float], interval: float, what: str) -> Dict[str, Any]:
    """Call `fetch` every `interval` seconds until `status_of` its answer is
    no longer live, or `timeout` seconds have passed (then `GwenlakeException`)."""
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        job = fetch()
        if status_of(job) not in LIVE_STATES:
            return job
        if deadline is not None and time.monotonic() >= deadline:
            raise GwenlakeException(f"{what} still {status_of(job)} after {timeout:.0f}s")
        time.sleep(interval)


async def poll_async(fetch, *, status_of, timeout, interval, what) -> Dict[str, Any]:
    import asyncio

    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        job = await fetch()
        if status_of(job) not in LIVE_STATES:
            return job
        if deadline is not None and time.monotonic() >= deadline:
            raise GwenlakeException(f"{what} still {status_of(job)} after {timeout:.0f}s")
        await asyncio.sleep(interval)
