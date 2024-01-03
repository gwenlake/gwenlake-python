from __future__ import annotations

# import base64
from typing import TYPE_CHECKING, List, Union, Iterable, Any
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
    ):
        
        payload = {
            "messages": messages,
            "model": model,
        }

        resp = self._client._request("POST", "/chat/completions", json=payload)            
        return resp.json()


    def stream(
        self,
        messages: List,
        model: Union[str, Literal["gpt-35-turbo-16k"]],
    ):
        
        payload = {
            "messages": messages,
            "model": model,
            "stream": True,
        }

        resp = self._client._stream("POST", "/chat/completions", json=payload)
        for streamed_response in resp:
            yield streamed_response
 
