import json
import httpx
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, Iterator, AsyncIterator, Union, IO, Tuple, Mapping, Sequence, TypeVar
from urllib.parse import quote

from gwenlake.version import __version__
from gwenlake.constants import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, DEFAULT_CONNECTION_LIMITS
from gwenlake.auth.credentials import Credentials


# duplicate of the above but without our custom file support
HttpxFileContent = Union[IO[bytes], bytes]
HttpxFileTypes = Union[
    # file (or bytes)
    HttpxFileContent,
    # (filename, file (or bytes))
    Tuple[Optional[str], HttpxFileContent],
    # (filename, file (or bytes), content_type)
    Tuple[Optional[str], HttpxFileContent, Optional[str]],
    # (filename, file (or bytes), content_type, headers)
    Tuple[Optional[str], HttpxFileContent, Optional[str], Mapping[str, str]],
]
HttpxRequestFiles = Union[Mapping[str, HttpxFileTypes], Sequence[Tuple[str, HttpxFileTypes]]]


class RequestOptions(BaseModel):
    method: str
    url: str
    path_params: Optional[Dict[str, Any]] = {}
    params: Optional[Dict[str, Any]] = {}
    headers: Optional[Dict[str, Any]] = {}
    max_retries: Optional[int] = None
    timeout: Optional[float] = None
    json_data: Optional[Dict[str, Any]] = None
    files: Optional[HttpxRequestFiles] = None
    follow_redirects: Optional[bool] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


_HttpxClientT = TypeVar("_HttpxClientT", bound=Union[httpx.Client, httpx.AsyncClient])

class BaseApiClient:

    _client: _HttpxClientT

    def __init__(
        self,
        *,
        base_url: str,
        credentials: Credentials,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self._base_url = base_url
        self._credentials = credentials
        self._max_retries = max_retries
        self._timeout = timeout

    def _create_url(self, request_info: RequestOptions) -> str:
        url = request_info.url
        path_params = request_info.path_params or {}

        for k, v in path_params.items():
            url = url.replace(f"{{{k}}}", quote(str(v), safe=""))

        return url

    def _create_headers(self, request_info: RequestOptions) -> Dict[str, Any]:
        headers = {
            "User-Agent": f"gwenlake/{__version__}",
            "Authorization": "Bearer " + self._credentials.get_token().access_token,
        }
        
        if request_info.headers:
            for key, value in request_info.headers.items():
                if value is None:
                    continue
                if isinstance(value, datetime):
                    headers[key] = value.astimezone(timezone.utc).isoformat()
                elif isinstance(value, (bytes, str)):
                    headers[key] = value
                else:
                    headers[key] = json.dumps(value)
        
        return headers

    def _build_request(self, request_info: RequestOptions) -> httpx.Request:
        return self._client.build_request(
            method=request_info.method,
            url=self._create_url(request_info),
            headers=self._create_headers(request_info),
            params=request_info.params,
            json=request_info.json_data,
            files=request_info.files,
            timeout=request_info.timeout or self._timeout,
        )

class ApiClient(BaseApiClient):

    _client: httpx.Client

    def __init__(
        self,
        *,
        base_url: str,
        credentials: Credentials,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT,
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
            limits=DEFAULT_CONNECTION_LIMITS,
        )

    def send(self, request_info: RequestOptions) -> Any:
        request = self._build_request(request_info)
        return self._client.send(request=request, stream=False)

    def stream(self, request_info: RequestOptions) -> Iterator[str]:
        request = self._build_request(request_info)
        with self._client.send(request=request, stream=True) as response:
            for line in response.iter_lines():
                yield line

class AsyncApiClient(BaseApiClient):

    _client: httpx.AsyncClient

    def __init__(
        self,
        *,
        base_url: str,
        credentials: Credentials,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT,
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
            limits=DEFAULT_CONNECTION_LIMITS,
        )

    async def send(self, request_info: RequestOptions) -> Any:
        request = self._build_request(request_info)
        return await self._client.send(request=request, stream=False)

    async def stream(self, request_info: RequestOptions) -> AsyncIterator[str]:
        request = self._build_request(request_info)
        async with self._client.send(request=request, stream=True) as response:
            async for line in response.iter_lines():
                yield line