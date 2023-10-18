import logging
import numpy as np
import base64
from typing import List
from tenacity import retry, stop_after_attempt, wait_random_exponential

from gwenlake.client import Client

logger = logging.getLogger(__name__)


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def get_embeddings(inputs: List[str], model_id="intfloat/e5-base-v2") -> List[List[float]]:
    payload = { "input": [ text.replace("\n", " ") for text in inputs ], "model": model_id }
    response = Client().fetch(f"/embeddings", payload=payload, method="post")
    if response:
        if "data" in response:
            # for data in response.data:
            #     if type(data["embedding"]) == str:
            #         data["embedding"] = np.frombuffer(
            #             base64.b64decode(data["embedding"]), dtype="float32"
            #         ).tolist()
            return [d["embedding"] for d in response["data"]]
    return None