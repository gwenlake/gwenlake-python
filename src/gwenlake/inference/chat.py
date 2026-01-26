from __future__ import annotations

# import base64
import json
from typing import TYPE_CHECKING, List, Union, Iterable, Any, Optional
from typing_extensions import Literal

from gwenlake.core.api_client import ApiClient, AsyncApiClient, RequestInfo


__all__ = ["Chat"]



class Chat:

    def __init__(self, client: ApiClient):
        self._client = client

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
            return self._client.stream("POST", "/chat/completions", json=payload)

        response = self._client.send("POST", "/chat/completions", json=payload)            
        return response.json()


class AsyncChat:

    def __init__(self, client: AsyncApiClient):
        self._client = client

    async def create(
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
            return self._client.stream("POST", "/chat/completions", json=payload)

        response = self._client.send("POST", "/chat/completions", json=payload)            
        return response.json()
