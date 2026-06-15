from typing import Optional, List, Dict, Any, Union, AsyncIterator

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions


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
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        
        payload = { 
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        
        if response_format:
            payload["response_format"] = response_format

        request_info = RequestOptions(
            method="POST",
            url="/chat/completions",
            headers={"Content-Type": "application/json"},
            json_data=payload,
        )

        if stream:
            return self._client.stream(request_info)

        response = self._client.send(request_info)
        response.raise_for_status()
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
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        
        payload = { 
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        
        if response_format:
            payload["response_format"] = response_format

        request_info = RequestOptions(
            method="POST",
            url="/chat/completions",
            headers={"Content-Type": "application/json"},
            json_data=payload,
        )

        if stream:
            return self._client.stream(request_info)

        response = await self._client.send(request_info)
        response.raise_for_status()
        return response.json()
