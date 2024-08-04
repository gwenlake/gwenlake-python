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
        *,
        messages: List = [],
        model: str,
        temperature: float = 0.0,
    ):
        
        payload = { "model": model }
        if messages:
            payload["messages"] = messages
        if temperature:
            payload["temperature"] = temperature

        response = self._client._request("POST", "/chat/completions", json=payload)            
        return response.json()


    def stream(
        self,
        messages: List,
        model: str,
        data: Optional[str] = None, 
    ):
        
        payload = {
            "messages": messages,
            "model": model,
            "stream": True,
        }
        if data:
            payload["data"] = data

        response = self._client._stream("POST", "/chat/completions", json=payload)
        for chunk in response:
            yield json.loads(chunk)
 
