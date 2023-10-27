import logging
import numpy as np
import base64
from typing import List

from gwenlake.client import Client

logger = logging.getLogger(__name__)


def get_embeddings(inputs: List[str], model_id="intfloat/e5-base-v2") -> List[List[float]]:
    return Client().get_embeddings(inputs=inputs, model_id=model_id)
    # payload = { "input": [ text.replace("\n", " ") for text in inputs ], "model": model_id }
    # response = Client().fetch(f"/embeddings", payload=payload, method="post")
    # if response:
    #     if "data" in response:
    #         return [d["embedding"] for d in response["data"]]
    # return None