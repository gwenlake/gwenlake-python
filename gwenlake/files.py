from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .exceptions import GwenlakeError
from .resource import Resource
from .schema import FileMeta


if TYPE_CHECKING:
    from .client import Client


__all__ = ["Files"]



class Files(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)


    def _build_path(self, file: str, prefix, str = None):
        if not prefix:
            prefix = os.path.dirname(file).strip(".").strip("/")
        return f"{ prefix.strip('/') }"


    def list(self, ref: str, file: str = None):
        url = f"/files/{ ref.strip('/') }/"
        if file:
            url += file.strip("/")
        resp = self._client._request("GET", url)
        obj = resp.json()
        return obj.get("data")


    def get(self, ref: str):
        url = f"/files/{ ref.strip('/') }"
        return self._client._request("GET", url)


    # def upload(self, ref: str, file: str, prefix: str = "/"):
    #     if not isinstance(file, str):
    #         raise ValueError("file must be a string")
    #     url = f"/files/{ ref.strip('/') }/" + self._build_path(file, prefix)
    #     resp = self._client._request("POST", url, files={"file": open(file, "rb")})
    #     return resp.json()

    def upload(self, ref: str, file: str, meta: dict = {}):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        url = f"/files/{ ref.strip('/') }/"
        resp = self._client._request("POST", url, files={"file": open(file, "rb")}, params=meta)
        return resp.json()
