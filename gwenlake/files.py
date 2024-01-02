from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .resource import SyncAPIResource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Files"]



class Files(SyncAPIResource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

    def create(
        self,
        *,
        owner: str,
        slug: str,
        file: str,
        prefix: str = None
    ):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        if not prefix:
            prefix = os.path.dirname(file).strip(".").strip("/")
        resp = self._client._request("POST", f"/files/{ owner }/{ slug }?prefix={prefix}", files={"file": open(file, "rb")})
        resp.raise_for_status()
        return f"/files/{ owner }/{ slug }/{ os.path.basename(file) }"

    def retrieve(
        self,
        *,
        owner: str,
        slug: str,
        file: str,
    ):
        url = f"/files/{ owner }/{ slug }/" + os.path.basename(file)
        resp = self._client._request("GET", url)
        resp.raise_for_status()
        return resp
