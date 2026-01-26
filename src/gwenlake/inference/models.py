import json
from typing import TYPE_CHECKING, List, Dict, Any, Union, Iterator

from gwenlake.core.api_client import ApiClient, AsyncApiClient, RequestInfo


__all__ = ["Models"]



class Models:

    def __init__(self, client: ApiClient):
        self._client = client


    def list(self) -> List[Dict[str, Any]]:
        response = self._client.send(
            RequestInfo(method="GET", path=f"/models")
        )
        response.raise_for_status()
        obj = response.json()
        return obj["data"]

    def run(self, *,
        model: str,
        input: Union[str, Any, List[Any]],
        stream: bool = False,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
    
        payload = {
            "input": input,
            "model": model,
            "stream": stream
        }
        
        request_info = RequestInfo(
            method="POST",
            path="/models",
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload),
        )

        if stream:
            return self._client.stream(request_info)

        response = self._client.send(request_info)
        response.raise_for_status()
        return response.json()

class AsyncModels:

    def __init__(self, client: AsyncApiClient):
        self._client = client


    async def list(self) -> List[Dict[str, Any]]:
        response = await self._client.send(
            RequestInfo(method="GET", path=f"/models")
        )
        response.raise_for_status()
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

        request_info = RequestInfo(
            method="POST",
            path="/models",
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload),
        )

        if stream:
            return self._client.stream(request_info)

        response = await self._client.send(request_info)
        response.raise_for_status()
        return response.json()
