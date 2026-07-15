import json
import httpx
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, Iterator, AsyncIterator, Union, IO, Tuple, Mapping, Sequence, TypeVar
from urllib.parse import quote

from gwenlake.version import __version__
from gwenlake.constants import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, DEFAULT_CONNECTION_LIMITS
from gwenlake.credentials import Credentials


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
        credentials: Optional[Credentials] = None,
        user_token: Optional[str] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self._base_url = base_url
        self._credentials = credentials
        self._user_token = user_token
        self._max_retries = max_retries
        self._timeout = timeout

    def _create_url(self, request_info: RequestOptions) -> str:
        url = request_info.url
        path_params = request_info.path_params or {}

        for k, v in path_params.items():
            url = url.replace(f"{{{k}}}", quote(str(v), safe=""))

        return url

    def _create_headers(self, request_info: RequestOptions) -> Dict[str, Any]:
        headers = {"User-Agent": f"gwenlake/{__version__}"}
        if self._user_token:
            headers["x-user"] = self._user_token
        elif self._credentials is not None:
            headers["Authorization"] = "Bearer " + self._credentials.get_token().access_token

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
        credentials: Optional[Credentials] = None,
        user_token: Optional[str] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        super().__init__(
            base_url=base_url,
            credentials=credentials,
            user_token=user_token,
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
        credentials: Optional[Credentials] = None,
        user_token: Optional[str] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        super().__init__(
            base_url=base_url,
            credentials=credentials,
            user_token=user_token,
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


# ---------------------------------------------------------------------------
# High-level unified client
# ---------------------------------------------------------------------------

import os

from gwenlake.exceptions import GwenlakeException
from gwenlake.models import Models, AsyncModels
from gwenlake.chat import Chat, AsyncChat
from gwenlake.embeddings import Embeddings, AsyncEmbeddings
from gwenlake.datasets import Datasets, AsyncDatasets
from gwenlake.files import Files, AsyncFiles
from gwenlake.projects import Projects, AsyncProjects
from gwenlake.statements import Statements, AsyncStatements


# Single gateway: every resource (inference + catalog) is served under /v1, so
# the base URL carries the version and resource paths are version-agnostic
# (/models, /datasets, /filesystem/..., /sql/...).
DEFAULT_BASE_URL = "https://api.gwenlake.com/v1"


def _resolve_credentials(
    api_key: Optional[str] = None,
    credentials: Optional[Credentials] = None,
    profile: Optional[str] = None,
) -> Credentials:
    """Resolve credentials from (in order): an explicit Credentials object, an
    api_key (or token), a named profile, the GWENLAKE_API_KEY env var, then the
    'default' profile in ~/.gwenlake/credentials."""
    if credentials is not None:
        return credentials
    if api_key is not None:
        return Credentials(token=api_key)
    if profile is not None:
        creds = Credentials.from_profile(profile)
        if creds is None or not creds.is_configured:
            raise GwenlakeException(
                f"No usable credentials for profile '{profile}' in ~/.gwenlake/credentials"
            )
        return creds

    env_key = os.environ.get("GWENLAKE_API_KEY")
    if env_key:
        return Credentials(token=env_key)

    creds = Credentials.from_profile("default")
    if creds is not None and creds.is_configured:
        return creds

    raise GwenlakeException(
        "No credentials provided. Pass api_key=..., credentials=... or profile=..., "
        "set the GWENLAKE_API_KEY environment variable, or configure ~/.gwenlake/credentials."
    )


def _resolve_base_url(base_url: Optional[str] = None) -> str:
    return base_url or os.environ.get("GWENLAKE_BASE_URL") or DEFAULT_BASE_URL


def _resolve_user_token(user_token: Optional[str] = None) -> Optional[str]:
    """A pre-validated `x-user` identity for internal, in-cluster callers.

    When set (constructor arg or `GWENLAKE_USER_TOKEN`), the client talks to the
    service directly as this identity — no api_key/credentials required. The
    catalog build runner injects it so transform code can call the API as the
    user who triggered the build without minting a real API key.
    """
    return user_token or os.environ.get("GWENLAKE_USER_TOKEN")


class Gwenlake:
    """Unified Gwenlake client exposing every API resource through a single
    authenticated transport (inference + catalog via one gateway)."""

    models: Models
    chat: Chat
    embeddings: Embeddings
    datasets: Datasets
    files: Files
    projects: Projects
    statements: Statements

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        credentials: Optional[Credentials] = None,
        profile: Optional[str] = None,
        user_token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        # Internal x-user mode (in-cluster) bypasses api-key/OAuth resolution.
        self._user_token = _resolve_user_token(user_token)
        self._credentials = (
            None if self._user_token
            else _resolve_credentials(api_key=api_key, credentials=credentials, profile=profile)
        )
        self._base_url = _resolve_base_url(base_url)
        self._client = ApiClient(
            base_url=self._base_url,
            credentials=self._credentials,
            user_token=self._user_token,
            max_retries=max_retries,
            timeout=timeout,
        )

        self.models = Models(self._client)
        self.chat = Chat(self._client)
        self.embeddings = Embeddings(self._client)
        self.datasets = Datasets(self._client)
        self.files = Files(self._client)
        self.projects = Projects(self._client)
        self.statements = Statements(self._client)


class AsyncGwenlake:
    """Asynchronous counterpart of :class:`Gwenlake`."""

    models: AsyncModels
    chat: AsyncChat
    embeddings: AsyncEmbeddings
    datasets: AsyncDatasets
    files: AsyncFiles
    projects: AsyncProjects
    statements: AsyncStatements

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        credentials: Optional[Credentials] = None,
        profile: Optional[str] = None,
        user_token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        # Internal x-user mode (in-cluster) bypasses api-key/OAuth resolution.
        self._user_token = _resolve_user_token(user_token)
        self._credentials = (
            None if self._user_token
            else _resolve_credentials(api_key=api_key, credentials=credentials, profile=profile)
        )
        self._base_url = _resolve_base_url(base_url)
        self._client = AsyncApiClient(
            base_url=self._base_url,
            credentials=self._credentials,
            user_token=self._user_token,
            max_retries=max_retries,
            timeout=timeout,
        )

        self.models = AsyncModels(self._client)
        self.chat = AsyncChat(self._client)
        self.embeddings = AsyncEmbeddings(self._client)
        self.datasets = AsyncDatasets(self._client)
        self.files = AsyncFiles(self._client)
        self.projects = AsyncProjects(self._client)
        self.statements = AsyncStatements(self._client)