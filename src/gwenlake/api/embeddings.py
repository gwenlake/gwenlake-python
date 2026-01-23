from __future__ import annotations

# import base64
from typing import TYPE_CHECKING, List, Union
from typing_extensions import Literal

from gwenlake.base.types import EmbeddingResponse, Embedding, Usage
from gwenlake.client.resource import Resource
if TYPE_CHECKING:
    from gwenlake.client.main import Client


__all__ = ["Embeddings"]


BATCH_SIZE = 100


class Embeddings(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

   
    def create(
        self,
        *,
        input: Union[str, List[str], List[int], List[List[int]]],
        model: Union[str, Literal["e5-base-v2"]],
    ) -> EmbeddingResponse:
        
        embeddings = []
        index = 0
        usage = Usage()

        for i in range(0, len(input), BATCH_SIZE):

            i_end = min(len(input), i+BATCH_SIZE)
            batch = input[i:i_end]

            payload = {
                "input": batch,
                "model": model,
            }

            resp = self._client._request("POST", "/embeddings", json=payload)
            
            obj = resp.json()

            for e in obj["data"]:
                e = Embedding(**e)
                e.index = index
                embeddings.append(e)
                index += 1

            if "usage" in obj:
                usage.prompt_tokens += obj["usage"].get("prompt_tokens")
                usage.total_tokens += obj["usage"].get("total_tokens")

        return EmbeddingResponse(data=embeddings, model=model, usage=usage, object="list")
