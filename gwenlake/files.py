from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Files"]



class Files(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

    def upload(self, ref: str, file: str, prefix: str = None):
        ref = ref.strip("/")
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        if not prefix:
            prefix = os.path.dirname(file).strip(".").strip("/")

        resp = self._client._request("POST", f"/files/{ ref }?prefix={prefix}", files={"file": open(file, "rb")})

        
        return f"/files/{ ref }/{ os.path.basename(file) }"

    def retrieve(self, ref: str, file: str):
        ref = ref.strip("/")
        url = f"/files/{ ref }/" + os.path.basename(file)

        resp = self._client._request("GET", url)

        return resp
