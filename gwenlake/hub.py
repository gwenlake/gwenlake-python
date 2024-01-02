from __future__ import annotations

from typing import TYPE_CHECKING

from langchain.prompts import PromptTemplate


from .resource import SyncAPIResource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Hub"]



class Hub(SyncAPIResource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

    def pull(self, repo: str):
        resp = self._client._request("GET", f"/hub/{ repo }")
        resp.raise_for_status()

        data = resp.json()

        if data.get("object") == "prompt" and data.get("template"):
            return PromptTemplate.from_template(data["template"])

        return data
