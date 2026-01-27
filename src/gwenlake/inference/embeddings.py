from typing import List, Union

from gwenlake.api_client import ApiClient, AsyncApiClient, RequestOptions
from gwenlake.types import EmbeddingResponse, Embedding, Usage

BATCH_SIZE = 100

class Embeddings:

    def __init__(self, client: ApiClient):
        self._client = client
    
    def create(
        self,
        *,
        input: Union[str, List[str], List[int], List[List[int]]],
        model: str,
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
            # json_payload = json.dumps(payload)

            response = self._client.send(
                RequestOptions(
                    method="POST",
                    url="/embeddings",
                    headers={'Content-Type': 'application/json'},
                    json_data=payload,
                )
            )
            response.raise_for_status()
            obj = response.json()

            for e in obj["data"]:
                e = Embedding(**e)
                e.index = index
                embeddings.append(e)
                index += 1

            if "usage" in obj:
                usage.prompt_tokens += obj["usage"].get("prompt_tokens")
                usage.total_tokens += obj["usage"].get("total_tokens")

        return EmbeddingResponse(data=embeddings, model=model, usage=usage, object="list")


class AsyncEmbeddings:

    def __init__(self, client: AsyncApiClient):
        self._client = client
    
    async def create(
        self,
        *,
        input: Union[str, List[str], List[int], List[List[int]]],
        model: str,
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

            
            response = await self._client.send(
                RequestOptions(
                    method="POST",
                    url="/embeddings",
                    headers={'Content-Type': 'application/json'},
                    data=payload,
                )
            )
            response.raise_for_status()
            obj = response.json()

            for e in obj["data"]:
                e = Embedding(**e)
                e.index = index
                embeddings.append(e)
                index += 1

            if "usage" in obj:
                usage.prompt_tokens += obj["usage"].get("prompt_tokens")
                usage.total_tokens += obj["usage"].get("total_tokens")

        return EmbeddingResponse(data=embeddings, model=model, usage=usage, object="list")