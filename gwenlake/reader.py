from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .exceptions import GwenlakeError
from .resource import Resource
from .schema import FileMeta


if TYPE_CHECKING:
    from .client import Client


__all__ = ["Reader"]



class Reader(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

    def get(self, file: str):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        resp = self._client._request("POST", "/text/reader", files={"file": (file, open(file, "rb"))})
        return resp.json()
