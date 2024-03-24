from __future__ import annotations

from typing import TYPE_CHECKING

from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Datasets"]



class Datasets(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)


    def list(self, ref: str):
        resp = self._client._request("GET", f"/datasets/{ ref }")
        obj = resp.json()
        return obj.get("data")


    def get(self, ref: str):
        resp = self._client._request("GET", f"/datasets/{ ref }")
        return resp.json()


    def search(self, ref: str, query: dict = {}):
        resp = self._client._request("POST", f"/datasets/{ ref }/search", json=query)
        obj = resp.json()
        return obj.get("data")
