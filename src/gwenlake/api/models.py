from __future__ import annotations

import json
# import base64
from typing import TYPE_CHECKING, List, Dict, Any, Union
from typing_extensions import Literal

from gwenlake.client.resource import Resource
if TYPE_CHECKING:
    from gwenlake.client.main import Client


__all__ = ["Models"]



class Models(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

   
    def list(self):
        resp = self._client._request("GET", f"/models")
        obj = resp.json()
        return obj["data"]

    def create(self, *,
        model: str,
        input: Union[str, Any, List[Any]],
        stream: bool = False,
    ):
    
        payload = {
            "input": input,
            "model": model,
            "stream": stream
        }
        if stream:
            return self._client._stream("POST", "/models", json=payload)

        response = self._client._request("POST", "/models", json=payload)
        return response.json()

    def run(self, *,
        model: str,
        input: Union[str, Any, List[Any]],
        stream: bool = False,
    ):
        return self.create(model=model, input=input, stream=stream)

