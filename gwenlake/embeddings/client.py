from typing import Any, Dict, List, Optional


from gwenlake.client import Client

def get_embeddings(inputs: List[str], model_id="intfloat/e5-base-v2") -> List[List[float]]:
    return Client().embed(inputs=inputs, model_id=model_id)
