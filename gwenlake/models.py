import logging
from typing import Optional, Union, Sequence, Tuple, List
from tenacity import retry, stop_after_attempt, wait_random_exponential

from gwenlake.client import Client

logger = logging.getLogger(__name__)


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def list_models():
    resp = Client().fetch("/models")
    if resp:
        return resp["data"]
    return None

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def run_model(model_id, inputs):
    response = Client().fetch(f"/models/{model_id}", payload=inputs, method="post")
    if response:
        return response["data"]
    return None

