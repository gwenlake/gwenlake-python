import os
import logging
from typing import Optional

from gwenlake import __version__
from gwenlake.core.exceptions import GwenlakeException
from gwenlake.core.credentials import Credentials
from gwenlake.core.api_client import ApiClient, AsyncApiClient
from gwenlake.inference.embeddings import Embeddings, AsyncEmbeddings
from gwenlake.inference.models import Models, AsyncModels



logger = logging.getLogger(__name__)


class InferenceClient:

    models: Models
    embeddings: Embeddings

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:

        super().__init__()

        self._api_key = api_key    
        if self._api_key is None:
            self._api_key = os.environ.get("GWENLAKE_API_KEY")
        if self._api_key is None:
            raise GwenlakeException(
                "The api_key client option must be set either by passing api_key to the client or by setting the GWENLAKE_API_KEY environment variable"
            )
        self._credentials = Credentials(token=self._api_key)

        self._base_url = base_url
        if self._base_url is None:
            self._base_url = os.environ.get("GWENLAKE_BASE_URL")
        if self._base_url is None:
            self._base_url = f"https://api.gwenlake.com/v1"

        self._timeout = timeout

        # API Client
        self._client = ApiClient(
            base_url=self._base_url,
            credentials=self._credentials,
        )

        self.models = Models(self._client)
        self.embeddings = Embeddings(self._client)


class AsyncInferenceClient:

    models: AsyncModels
    embeddings: AsyncEmbeddings

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:

        super().__init__()

        self._api_key = api_key    
        if self._api_key is None:
            self._api_key = os.environ.get("GWENLAKE_API_KEY")
        if self._api_key is None:
            raise GwenlakeException(
                "The api_key client option must be set either by passing api_key to the client or by setting the GWENLAKE_API_KEY environment variable"
            )
        self._credentials = Credentials(token=self._api_key)

        self._base_url = base_url
        if self._base_url is None:
            self._base_url = os.environ.get("GWENLAKE_BASE_URL")
        if self._base_url is None:
            self._base_url = f"https://api.gwenlake.com/v1"

        self._timeout = timeout

        # API Client
        self._client = AsyncApiClient(
            base_url=self._base_url,
            credentials=self._credentials,
        )

        self.models = Models(self._client)
        self.embeddings = AsyncEmbeddings(self._client)