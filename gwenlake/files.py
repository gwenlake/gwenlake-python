from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .exceptions import GwenlakeError
from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Files"]



class Files(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)


    def _build_path(self, file: str, prefix, str = None):
        if not prefix:
            prefix = os.path.dirname(file).strip(".").strip("/")
        return f"/{ prefix.strip('/') }"


    def upload(self, ref: str, file: str, prefix: str = None):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        url = f"/hub/{ ref.strip('/') }/tree/main" + self._build_path(file, prefix)
        resp = self._client._request("POST", url, files={"file": open(file, "rb")})
        return resp.json()


    def list(self, ref: str, file: str):
        url = f"/hub/{ ref.strip('/') }/tree/main/" + file.strip("/")
        resp = self._client._request("GET", url)
        return resp.json()


    def retrieve(self, ref: str, file: str):
        url = f"/hub/{ ref.strip('/') }/blob/main/" + file.strip("/")
        return self._client._request("GET", url)
