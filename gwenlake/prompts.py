from __future__ import annotations

from typing import TYPE_CHECKING

from langchain.prompts import PromptTemplate


from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Prompts"]



class Prompts(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)


    def list(self, ref: str):
        resp = self._client._request("GET", f"/prompts/{ ref }")
        obj = resp.json()
        return obj.get("data")


    def get(self, ref: str):
        resp = self._client._request("GET", f"/prompts/{ ref }")
        obj = resp.json()
        return PromptTemplate.from_template(obj["template"])
