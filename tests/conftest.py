"""A client whose transport answers from a scripted catalog: every request is
recorded (method, path, query, JSON body) and answered from `routes`, so a
test can say what the SDK sent and what it made of the answer."""

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from gwenlake import Gwenlake


class FakeApi:
    """`routes`: {(METHOD, path): answer} where answer is a dict/list (-> 200
    JSON), bytes (-> 200 raw), an int (-> that status, empty body), a tuple
    (status, body) or a callable(request) -> httpx.Response."""

    def __init__(self, routes: Optional[Dict[Tuple[str, str], Any]] = None):
        self.routes = dict(routes or {})
        self.calls: List[Dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = urlparse(str(request.url)).path.replace("/v1", "", 1)
        query = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(urlparse(str(request.url)).query).items()}
        body = None
        if request.content and request.headers.get("content-type", "").startswith("application/json"):
            body = json.loads(request.content)
        self.calls.append({"method": request.method, "path": path, "query": query, "json": body,
                           "headers": dict(request.headers), "content": request.content})
        answer = self.routes.get((request.method, path))
        if answer is None:
            # a templated route: "/datasets/{id}" matches any one segment
            for (method, template), candidate in self.routes.items():
                if method == request.method and re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", template), path):
                    answer = candidate
                    break
        if answer is None:
            return httpx.Response(404, json={"detail": f"no route {request.method} {path}"}, request=request)
        if callable(answer):
            return answer(request)
        if isinstance(answer, tuple):
            status, payload = answer
            return httpx.Response(status, json=payload, request=request)
        if isinstance(answer, int):
            return httpx.Response(answer, request=request)
        if isinstance(answer, (bytes, bytearray)):
            return httpx.Response(200, content=bytes(answer), request=request)
        return httpx.Response(200, json=answer, request=request)

    def last(self) -> Dict[str, Any]:
        return self.calls[-1]

    def paths(self) -> List[str]:
        return [f"{c['method']} {c['path']}" for c in self.calls]


def fake_client(api: FakeApi) -> Gwenlake:
    client = Gwenlake(api_key="test-key", base_url="https://api.test/v1")
    client._client._client = httpx.Client(base_url="https://api.test/v1", transport=httpx.MockTransport(api.handler))
    return client


@pytest.fixture
def api():
    return FakeApi()


@pytest.fixture
def client(api):
    return fake_client(api)
