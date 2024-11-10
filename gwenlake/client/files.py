from __future__ import annotations

import os
from typing import TYPE_CHECKING

from gwenlake.base.types import FileMeta
from gwenlake.client.resource import Resource
if TYPE_CHECKING:
    from gwenlake.client.main import Client


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

    def get(self, filepath: str):
        url = f"/files/{ filepath.strip('/') }"
        return self._client._request("GET", url)

    def put(self, file: str, path: str = "", meta: dict = {}):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        url = "/files"
        if path:
            url = f"/files/{ path.strip('/') }"
        try:
            resp = self._client._request("POST", url, files={"file": open(file, "rb")}, params=meta)
            return resp.json()
        except Exception as e:
            print(e)
        return None
