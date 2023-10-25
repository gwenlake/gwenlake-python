import io
import os
import logging
import requests
from typing import Optional, Union, Sequence, Tuple, List
from tenacity import retry, stop_after_attempt, wait_random_exponential

from gwenlake.client import Client

logger = logging.getLogger(__name__)


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def upload_file(file: Union[str, Tuple[str, io.BytesIO]]):

    client = Client()

    if isinstance(file, str):
        with open(file, "rb") as f:
            files = {"file": f}
            response = client.session.post(
                client.api_url + "/data/uploadfiles",
                headers=client.headers,
                files=files,
            )
    elif isinstance(file, tuple):
        file_ = {"file": file}
        response = client.session.post(
            client.api_url + "/data/uploadfiles",
            headers=client.headers,
            files=file_,
        )
    else:
        raise ValueError("file must be a string or tuple")

    if response.status_code != 200:
        raise Exception

    result = response.json()
    if "detail" in result and "already exists" in result["detail"]:
        file_name = file if isinstance(file, str) else file[0]
        file_name = file_name.split("/")[-1]
        raise ValueError(f"Dataset {file_name} already exists")

    return result
