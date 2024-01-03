from __future__ import annotations

from typing import TYPE_CHECKING

from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Models"]



class Models(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

   
    # def list(self):
    #     resp = self._client._request("GET", "/models")
    #     obj = resp.json()
    #     return obj["data"]
       
    # def run(self, *,
    #     input: Union[str, List[str], List[int], List[List[int]]],
    #     model: Union[str, Literal["e5-base-v2"]],
    # ):
    #     embeddings = []
    #     index = 0
    #     usage = Usage()
    #     try:
    #         for i in range(0, len(input), BATCH_SIZE):
    #             i_end = min(len(input), i+BATCH_SIZE)
    #             batch = input[i:i_end]
    #             payload = {
    #                 "input": batch,
    #                 "model": model,
    #             }
    #             resp = self._client._request("POST", "/embeddings", json=payload)
    #             obj = resp.json()
    #             for e in obj["data"]:
    #                 e = Embedding(**e)
    #                 e.index = index
    #                 embeddings.append(e)
    #                 index += 1
    #             if "usage" in obj:
    #                 usage.prompt_tokens += obj["usage"].get("prompt_tokens")
    #                 usage.total_tokens += obj["usage"].get("total_tokens")
    #     except:
    #         return None
    #     return EmbeddingResponse(data=embeddings, model=model, usage=usage, object="list")
