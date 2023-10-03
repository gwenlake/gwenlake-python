import logging
from typing import List
from tenacity import retry, stop_after_attempt, wait_random_exponential

from gwenlake.client import Client

logger = logging.getLogger(__name__)


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def get_embeddings(inputs: List[str], model_id="e5-base-v2") -> List[List[float]]:
    payload = [ { "input": text.replace("\n", " ") } for text in inputs ]
    response = Client().fetch(f"/models/{model_id}", payload=payload, method="post")
    if response:
        if "data" in response:
            return [d["embedding"] for d in response["data"]]
    return None