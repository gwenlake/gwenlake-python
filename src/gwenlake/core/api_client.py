import json
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional, Dict, Any
from urllib.parse import quote

from gwenlake.core.httpclient import HttpClient, AsyncHttpClient
from gwenlake.core.credentials import Credentials


class RequestInfo(BaseModel):
    method: str
    path: str
    path_params: Optional[Dict[str, Any]] = {}
    params: Optional[Dict[str, Any]] = {}
    headers: Optional[Dict[str, Any]] = {}
    body: Optional[Any] = None
    files: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None
    stream: Optional[bool] = False



class BaseApiClient:

    def __init__(
        self, 
        credentials: Credentials,
        prefix: str = None
    ):
        self._credentials = credentials
        self._session = HttpClient(self._credentials.hostname)
        self._prefix = prefix

    def _create_url(self, request_info: RequestInfo) -> str:
        resource_path = request_info.path
        path_params = request_info.path_params

        for k, v in path_params.items():
            resource_path = resource_path.replace(f"{{{k}}}", quote(v, safe=""))

        if self.prefix:
            resource_path = f"{self._prefix}{resource_path}"

        return resource_path

    def _create_headers(self, request_info: RequestInfo) -> Dict[str, Any]:
        return {
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

    def __init__(self, credentials: Credentials, prefix: str = None):
        super().__init__(credentials, prefix)
        self._session = HttpClient(self._credentials.hostname)

    def call_api(self, request_info: RequestInfo) -> Any:
        request = self._session.build_request(
            method=request_info.method,
            url=self._create_url(request_info),
            headers=self._create_headers(request_info),
            params=request_info.params,
            content=request_info.body,
            files=request_info.files,
            timeout=request_info.timeout,
        )

        if not request_info.stream:
            return self._session.send(
                request=request,
                stream=False,
            )

        with self._session.send(request=request, stream=True) as response:
            for line in response.iter_lines():
                yield line

class AsyncApiClient(BaseApiClient):

    def __init__(self, credentials: Credentials, prefix: str = None):
        super().__init__(credentials, prefix)
        self._session = AsyncHttpClient(self._credentials.hostname)

    async def call_api(self, request_info: RequestInfo) -> Any:
        request = self._session.build_request(
            method=request_info.method,
            url=self._create_url(request_info),
            headers=self._create_headers(request_info),
            params=request_info.params,
            content=request_info.body,
            files=request_info.files,
            timeout=request_info.timeout,
        )

        if not request_info.stream:
            return await self._session.send(
                request=request,
                stream=False,
            )

        async with self._session.send(request=request, stream=True) as response:
            async for line in response.iter_lines():
                yield line