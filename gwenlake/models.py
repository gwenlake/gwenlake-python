from __future__ import annotations

# import base64
from typing import TYPE_CHECKING, List, Dict, Any, Union
from typing_extensions import Literal

from .schema import EmbeddingResponse, Embedding, Usage
from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Models"]



class Models(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

   
    def list(self):
        resp = self._client._request("GET", f"/models")
        obj = resp.json()
        return obj["data"]

    def create(self,
        input: Union[str, Any, List[Any]],
        model: str,
    ):
    
        payload = {
            "input": input,
            "model": model,
        }

        resp = self._client._request("POST", "/models", json=payload)

        return resp.json()
