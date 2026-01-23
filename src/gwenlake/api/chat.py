from __future__ import annotations

# import base64
import json
from typing import TYPE_CHECKING, List, Union, Iterable, Any, Optional
from typing_extensions import Literal

from gwenlake.client.resource import Resource
if TYPE_CHECKING:
    from gwenlake.client.main import Client


__all__ = ["Chat"]



class Chat(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

    def create(
        self,
        *,
        model: str,
        messages: List,
        temperature: float = 0.0,
        stream: bool = False,
        response_format: Optional[dict] = None,
    ):
        
        payload = { 
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
            }
        
        if response_format:
            payload["response_format"] = response_format

        if stream:
            return self._client._stream("POST", "/chat/completions", json=payload)

        response = self._client._request("POST", "/chat/completions", json=payload)            
        return response.json()
