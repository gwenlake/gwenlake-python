from typing import Optional

from gwenlake.constants import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT
from gwenlake.api_client import ApiClient, Credentials
from gwenlake.factory.datasets import DatasetsClient


class FactoryClient:

    def __init__(
            self, 
            *,
            credentials: Optional[Credentials] = None,
            base_url: Optional[str] = None,
            timeout: Optional[float] = DEFAULT_TIMEOUT,
            max_retries: int = DEFAULT_MAX_RETRIES,
        ):

        if credentials is None:
            credentials = Credentials.from_profile("default")

        self._client = ApiClient(
            base_url=base_url,
            credentials=credentials,
            max_retries=max_retries,
            timeout=timeout,
        )

        self.datasets = DatasetsClient(self._client)
