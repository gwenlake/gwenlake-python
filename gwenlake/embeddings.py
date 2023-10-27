import logging
from typing import List

from gwenlake.client import Client

logger = logging.getLogger(__name__)


def get_embeddings(inputs: List[str], model_id="intfloat/e5-base-v2") -> List[List[float]]:
    return Client().get_embeddings(inputs=inputs, model_id=model_id)
