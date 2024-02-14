import os
import random
import time
from datetime import datetime
import httpx
import logging
import pandas as pd
from typing import Any, Optional, List, Dict, Any, Mapping, Type, Union, Iterable, Iterator

from . import __version__
from .exceptions import GwenlakeError
from .constants import DEFAULT_TIMEOUT

from .embeddings import Embeddings
from .files import Files
from .prompts import Prompts
from .models import Models
from .datasets import Datasets
from .chat import Chat

import gwenlake


logger = logging.getLogger(__name__)


class Client:

    __client: Optional[httpx.Client] = None
    __async_client: Optional[httpx.AsyncClient] = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float | httpx.Timeout | None = DEFAULT_TIMEOUT,
        **kwargs,
        ) -> None:

        super().__init__()

        if api_key is None:
            api_key = gwenlake.api_key
        if api_key is None:
            api_key = os.environ.get("GWENLAKE_API_KEY")
        if api_key is None:
            raise GwenlakeError(
                "The api_key client option must be set either by passing api_key to the client or by setting the GWENLAKE_API_KEY environment variable"
            )
        self._api_key = api_key

        if base_url is None:
            base_url = gwenlake.base_url
        if base_url is None:
            base_url = os.environ.get("GWENLAKE_BASE_URL")
        if base_url is None:
            base_url = f"https://api.gwenlake.com/v1"
        self._base_url = base_url

        self._timeout = timeout
        self._client_kwargs = kwargs
                

    @property
    def _client(self) -> httpx.Client:
        if not self.__client:
            self.__client = _build_httpx_client(
                httpx.Client,
                self._api_key,
                self._base_url,
                self._timeout,
                **self._client_kwargs,
            )  # type: ignore[assignment]
        return self.__client  # type: ignore[return-value]

    @property
    def _async_client(self) -> httpx.AsyncClient:
        if not self.__async_client:
            self.__async_client = _build_httpx_client(
                httpx.AsyncClient,
                self._api_key,
                self._base_url,
                self._timeout,
                **self._client_kwargs,
            )  # type: ignore[assignment]
        return self.__async_client  # type: ignore[return-value]

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        resp = self._client.request(method, path, **kwargs)
        _raise_for_status(resp)
        return resp

    async def _async_request(self, method: str, path: str, **kwargs) -> httpx.Response:
        resp = await self._async_client.request(method, path, **kwargs)
        _raise_for_status(resp)
        return resp

    def _stream(self, method: str, path: str, **kwargs) -> Iterator[Dict[str, Any]]:
        with self._client.stream(method, path, **kwargs) as resp:
            for streamed_response in resp.iter_lines():
                yield streamed_response

    async def _async_stream(self, method: str, path: str, **kwargs) -> Iterator[Dict[str, Any]]:
        async with self._client.stream(method, path, **kwargs) as resp:
            async for streamed_response in resp.iter_lines():
                yield streamed_response

    @property
    def embeddings(self) -> Embeddings:
        return Embeddings(client=self)
    
    @property
    def files(self) -> Files:
        return Files(client=self)

    @property
    def prompts(self) -> Prompts:
        return Prompts(client=self)

    @property
    def models(self) -> Models:
        return Models(client=self)

    @property
    def datasets(self) -> Datasets:
        return Datasets(client=self)

    @property
    def chat(self) -> Chat:
        return Chat(client=self)


# Adapted from https://github.com/encode/httpx/issues/108#issuecomment-1132753155
class RetryTransport(httpx.AsyncBaseTransport, httpx.BaseTransport):
    """A custom HTTP transport that automatically retries requests using an exponential backoff strategy
    for specific HTTP status codes and request methods.
    """

    RETRYABLE_METHODS = frozenset(["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"])
    RETRYABLE_STATUS_CODES = frozenset(
        [
            429,  # Too Many Requests
            503,  # Service Unavailable
            504,  # Gateway Timeout
        ]
    )
    MAX_BACKOFF_WAIT = 60

    def __init__(  # pylint: disable=too-many-arguments
        self,
        wrapped_transport: Union[httpx.BaseTransport, httpx.AsyncBaseTransport],
        *,
        max_attempts: int = 10,
        max_backoff_wait: float = MAX_BACKOFF_WAIT,
        backoff_factor: float = 0.1,
        jitter_ratio: float = 0.1,
        retryable_methods: Optional[Iterable[str]] = None,
        retry_status_codes: Optional[Iterable[int]] = None,
    ) -> None:
        self._wrapped_transport = wrapped_transport

        if jitter_ratio < 0 or jitter_ratio > 0.5:
            raise ValueError(
                f"jitter ratio should be between 0 and 0.5, actual {jitter_ratio}"
            )

        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.retryable_methods = (
            frozenset(retryable_methods)
            if retryable_methods
            else self.RETRYABLE_METHODS
        )
        self.retry_status_codes = (
            frozenset(retry_status_codes)
            if retry_status_codes
            else self.RETRYABLE_STATUS_CODES
        )
        self.jitter_ratio = jitter_ratio
        self.max_backoff_wait = max_backoff_wait

    def _calculate_sleep(
        self, attempts_made: int, headers: Union[httpx.Headers, Mapping[str, str]]
    ) -> float:
        retry_after_header = (headers.get("Retry-After") or "").strip()
        if retry_after_header:
            if retry_after_header.isdigit():
                return float(retry_after_header)

            try:
                parsed_date = datetime.fromisoformat(retry_after_header).astimezone()
                diff = (parsed_date - datetime.now().astimezone()).total_seconds()
                if diff > 0:
                    return min(diff, self.max_backoff_wait)
            except ValueError:
                pass

        backoff = self.backoff_factor * (2 ** (attempts_made - 1))
        jitter = (backoff * self.jitter_ratio) * random.choice([1, -1])  # noqa: S311
        total_backoff = backoff + jitter
        return min(total_backoff, self.max_backoff_wait)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._wrapped_transport.handle_request(request)  # type: ignore

        if request.method not in self.retryable_methods:
            return response

        remaining_attempts = self.max_attempts - 1
        attempts_made = 1

        while True:
            if (
                remaining_attempts < 1
                or response.status_code not in self.retry_status_codes
            ):
                return response

            response.close()

            sleep_for = self._calculate_sleep(attempts_made, response.headers)
            time.sleep(sleep_for)

            response = self._wrapped_transport.handle_request(request)  # type: ignore

            attempts_made += 1
            remaining_attempts -= 1

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._wrapped_transport.handle_async_request(request)  # type: ignore

        if request.method not in self.retryable_methods:
            return response

        remaining_attempts = self.max_attempts - 1
        attempts_made = 1

        while True:
            if (
                remaining_attempts < 1
                or response.status_code not in self.retry_status_codes
            ):
                return response

            response.close()

            sleep_for = self._calculate_sleep(attempts_made, response.headers)
            time.sleep(sleep_for)

            response = await self._wrapped_transport.handle_async_request(request)  # type: ignore

            attempts_made += 1
            remaining_attempts -= 1

    async def aclose(self) -> None:
        await self._wrapped_transport.aclose()  # type: ignore

    def close(self) -> None:
        self._wrapped_transport.close()  # type: ignore


def _build_httpx_client(
    client_type: Type[Union[httpx.Client, httpx.AsyncClient]],
    api_key: str,
    base_url: str,
    timeout: Optional[httpx.Timeout] = DEFAULT_TIMEOUT,
    **kwargs,
) -> Union[httpx.Client, httpx.AsyncClient]:
    headers = {
        "User-Agent": f"gwenlake-python/{__version__}",
        "Authorization": f"Bearer {api_key}",
    }

    transport = kwargs.pop("transport", None) or (
        httpx.HTTPTransport()
        if client_type is httpx.Client
        else httpx.AsyncHTTPTransport()
    )

    return client_type(
        base_url=base_url,
        headers=headers,
        timeout=timeout,
        transport=RetryTransport(wrapped_transport=transport),  # type: ignore[arg-type]
        **kwargs,
    )


def _raise_for_status(resp: httpx.Response) -> None:
    if 400 <= resp.status_code < 600:
        raise GwenlakeError(resp.json()["detail"])
