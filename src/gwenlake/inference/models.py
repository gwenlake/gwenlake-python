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
        response = self._client.call_api(
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
            return self._client.stream_api(
                RequestInfo(
                    method="POST",
                    path="/models",
                    headers={'Content-Type': 'application/json'},
                    data=json_payload,
                    steal=True,
                )
            )

        response = self._client.call_api(
            RequestInfo(
                method="POST",
                path="/models",
                headers={'Content-Type': 'application/json'},
                data=json_payload,
                steal=True,
            )
        )
        return response.json()