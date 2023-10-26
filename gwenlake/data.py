import io
import os
import logging
import requests
from typing import Optional, Union, Sequence, Tuple, List
from tenacity import retry, stop_after_attempt, wait_random_exponential

from gwenlake.client import Client

logger = logging.getLogger(__name__)


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def upload(data_id: str, filename: str):
    if not isinstance(filename, str):
        raise ValueError("file must be a string")
    filepath = os.path.dirname(filename).strip(".").strip("/")
    url = f"/data/{data_id}/upload?filepath={filepath}"
    files = [('files', open(filename, "rb"))]
    return Client().fetch(url, files=files, method="post")
    
