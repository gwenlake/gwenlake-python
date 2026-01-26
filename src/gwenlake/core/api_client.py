import json
import httpx
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional, Dict, Any, Iterator, AsyncIterator, Callable
from urllib.parse import quote

from gwenlake.core.credentials import Credentials
from gwenlake.version import __version__


class RequestInfo(BaseModel):
    method: str
    path: str
    path_params: Optional[Dict[str, Any]] = {}
    params: Optional[Dict[str, Any]] = {}
    headers: Optional[Dict[str, Any]] = {}
    content: Optional[Any] = None
    data: Optional[Any] = None
    files: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None
    stream: Optional[bool] = False


class BaseApiClient:

    def __init__(
        self,
        *,
        base_url: str,
        credentials: Credentials,
        max_retries: int = None,
        timeout: int = None,
    ):
        self._base_url = base_url
        self._credentials = credentials
        self._max_retries = max_retries or 5
        self._timeout = timeout or 5

    def _create_url(self, request_info: RequestInfo) -> str:
        resource_path = request_info.path
        path_params = request_info.path_params

        for k, v in path_params.items():
            resource_path = resource_path.replace(f"{{{k}}}", quote(v, safe=""))

        return resource_path

    def _create_headers(self, request_info: RequestInfo) -> Dict[str, Any]:
        return {
            "User-Agent": f"gwenlake/{__version__}",
            "Authorization": "Bearer " + self._credentials.get_token().access_token,
            **{
                key: (
                    value.astimezone(timezone.utc).isoformat()
                    if isinstance(value, datetime)
                    else value if isinstance(value, (bytes, str)) else json.dumps(value)
                )
                for key, value in request_info.headers.items()
                if value is not None
            },
        }    


class ApiClient(BaseApiClient):

    def __init__(
        self,
        *,
        base_url: str,
        credentials: Credentials,
        max_retries: int = None,
        timeout: int = None,
    ):
        super().__init__(
            base_url=base_url,
            credentials=credentials,
            max_retries=max_retries,
            timeout=timeout
        )
        transport = httpx.HTTPTransport(retries=self._max_retries) 
        self._client = httpx.Client(
            base_url=base_url,
            transport=transport, 
            timeout=self._timeout,
            follow_redirects=True,
        )

    def call_api(self, request_info: RequestInfo) -> Any:
        request = self._client.build_request(
            method=request_info.method,
            url=self._create_url(request_info),
            headers=self._create_headers(request_info),
            params=request_info.params,
            content=request_info.content,
            data=request_info.data,
            files=request_info.files,
            timeout=request_info.timeout,
        )

        return self._client.send(
            request=request,
            stream=False,
        )

    def stream_api(self, request_info: RequestInfo) -> Iterator[Dict[str, Any]]:
        request = self._client.build_request(
            method=request_info.method,
            url=self._create_url(request_info),
            headers=self._create_headers(request_info),
            params=request_info.params,
            content=request_info.content,
            data=request_info.data,
            files=request_info.files,
            timeout=request_info.timeout,
        )

        with self._client.send(request=request, stream=True) as response:
            for streamed_response in response.iter_lines():
                yield streamed_response

class AsyncApiClient(BaseApiClient):

    def __init__(
        self,
        *,
        base_url: str,
        credentials: Credentials,
        max_retries: int = None,
        timeout: int = None,
    ):
        super().__init__(
            base_url=base_url,
            credentials=credentials,
            max_retries=max_retries,
            timeout=timeout
        )
        transport = httpx.HTTPTransport(retries=self._max_retries) 
        self._client = httpx.AsyncClient(
            base_url=base_url,
            transport=transport, 
            timeout=self._timeout,
            follow_redirects=True,
        )

    async def call_api(self, request_info: RequestInfo) -> Any:
        request = self._client.build_request(
            method=request_info.method,
            url=self._create_url(request_info),
            headers=self._create_headers(request_info),
            params=request_info.params,
            content=request_info.content,
            data=request_info.data,
            files=request_info.files,
            timeout=request_info.timeout,
        )

        return await self._client.send(
            request=request,
            stream=False,
        )

    async def stream_api(self, request_info: RequestInfo) -> AsyncIterator[Dict[str, Any]]:
        request = self._client.build_request(
            method=request_info.method,
            url=self._create_url(request_info),
            headers=self._create_headers(request_info),
            params=request_info.params,
            content=request_info.content,
            data=request_info.data,
            files=request_info.files,
            timeout=request_info.timeout,
        )

        async with self._client.send(request=request, stream=True) as response:
            async for streamed_response in response.iter_lines():
                yield streamed_response