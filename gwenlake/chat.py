from __future__ import annotations

# import base64
import json
from typing import TYPE_CHECKING, List, Union, Iterable, Any, Optional
from typing_extensions import Literal

from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Chat"]



class Chat(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

    def create(
        self,
        messages: List,
        model: Union[str, Literal["gpt-35-turbo-16k"]],
        data: Optional[str] = None, 
    ):
        
        payload = {
            "messages": messages,
            "model": model,
        }
        if data:
            payload["data"] = data

        resp = self._client._request("POST", "/chat/completions", json=payload)            
        return resp.json()


    def stream(
        self,
        messages: List,
        model: Union[str, Literal["gpt-35-turbo-16k"]],
        data: Optional[str] = None, 
    ):
        
        payload = {
            "messages": messages,
            "model": model,
            "stream": True,
        }
        if data:
            payload["data"] = data

        resp = self._client._stream("POST", "/chat/completions", json=payload)
        for streamed_response in resp:
            yield json.loads(streamed_response)
 
