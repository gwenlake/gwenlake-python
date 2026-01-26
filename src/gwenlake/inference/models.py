from __future__ import annotations

import json
# import base64
from typing import TYPE_CHECKING, List, Dict, Any, Union
from typing_extensions import Literal

from gwenlake.core.api_client import ApiClient, AsyncApiClient, RequestInfo


__all__ = ["Models"]



class Models:

    def __init__(self, client: ApiClient):
        self._client = client


    def list(self):
        response = self._client.send(
            RequestInfo(method="GET", path=f"/models")
        )
        obj = response.json()
        return obj["data"]

    def run(self, *,
        model: str,
        input: Union[str, Any, List[Any]],
        stream: bool = False,
    ):
    
        payload = {
            "input": input,
            "model": model,
            "stream": stream
        }

        json_payload = json.dumps(payload)
        
        if stream:
            return self._client.stream(
                RequestInfo(
                    method="POST",
                    path="/models",
                    headers={'Content-Type': 'application/json'},
                    data=json_payload,
                    stream=True,
                )
            )

        response = self._client.send(
            RequestInfo(
                method="POST",
                path="/models",
                headers={'Content-Type': 'application/json'},
                data=json_payload,
                stream=True,
            )
        )
        return response.json()


class AsyncModels:

    def __init__(self, client: AsyncApiClient):
        self._client = client


    async def list(self):
        response = await self._client.send(
            RequestInfo(method="GET", path=f"/models")
        )
        obj = response.json()
        return obj["data"]

    async def run(
        self,
        *,
        model: str,
        input: Union[str, Any, List[Any]],
        stream: bool = False,
    ):
    
        payload = {
            "input": input,
            "model": model,
            "stream": stream
        }

        json_payload = json.dumps(payload)
        
        if stream:
            return await self._client.stream(
                RequestInfo(
                    method="POST",
                    path="/models",
                    headers={'Content-Type': 'application/json'},
                    data=json_payload,
                    stream=True,
                )
            )

        response = await self._client.send(
            RequestInfo(
                method="POST",
                path="/models",
                headers={'Content-Type': 'application/json'},
                data=json_payload,
                stream=True,
            )
        )
        return response.json()