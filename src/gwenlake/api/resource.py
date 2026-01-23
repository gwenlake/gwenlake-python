from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gwenlake.client.main import Client


class Resource:

    _client: Client

    def __init__(self, client: Client) -> None:
        self._client = client

    def _sleep(self, seconds: float) -> None:
        time.sleep(seconds)
