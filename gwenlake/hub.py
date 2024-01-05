from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langchain.prompts import PromptTemplate


from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Hub"]



class Hub(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)



    def list(self, ref: str):
        resp = self._client._request("GET", f"/hub/{ ref }")
        obj = resp.json()
        return obj


    def pull(self, ref: str):
        
        resp = self._client._request("GET", f"/hub/{ ref }")

        obj = resp.json()

        if obj.get("object") == "prompt" and obj.get("template"):
            return PromptTemplate.from_template(obj["template"])

        return obj
