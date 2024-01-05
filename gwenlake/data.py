from __future__ import annotations

from typing import TYPE_CHECKING

from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Data"]



class Data(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

    def upload(self, ref: str, data: dict):
        resp = self._client._request("POST", f"/hub/{ ref }/uploaddata", json=data)
        return resp.json()
