import os
import json
import logging
import requests
import pandas as pd
from typing import Optional, List
from tenacity import retry, stop_after_attempt, wait_random_exponential

import gwenlake


TIMEOUT  = 20

logger = logging.getLogger(__name__)


class Client:

    def __init__(self, api_key: Optional[str] = None, api_base: Optional[str] = None, timeout: Optional[float] = TIMEOUT):
        self.api_key  = api_key or gwenlake.api_key
        self.api_base = api_base or gwenlake.api_base
        self.timeout  = timeout
        self.session  = requests.Session()
    
    
    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
    def fetch(self, query, payload: Optional[str] = None, files: Optional[list] = None, method: Optional[str] = "get"):
        url = f"{self.api_base}{query}"
        headers = { "Authorization": f"Bearer {self.api_key}" }
        if method == "post":
            if files:
                r = self.session.post(url, headers=headers, files=files, timeout=self.timeout)
            else:
                r = self.session.post(url, headers=headers, json=payload, timeout=self.timeout)
        else:
            r = self.session.get(url, headers=headers, json=payload, timeout=self.timeout)
        if r.status_code != 200:
            logger.exception("An error occurred while calling API.")
            raise Exception
        return r.json()


    def upload_file(self, team_name: str, project_name: str, file: str):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        path = os.path.dirname(file).strip(".").strip("/")
        url = f"/files/{ team_name }/{ project_name }/upload?path={path}"
        file_ = {"file": open(file, "rb")}
        return self.fetch(url, files=file_, method="post")

    def upload_data(self, data_id: str, data: []):
        url = f"/data/{ data_id }/uploaddata"
        payload = { "data": data }
        return self.fetch(url, payload=payload, method="post")
            
    def list_models(self):
        resp = self.fetch("/models")
        if resp:
            return resp["data"]
        return None

    def run_model(self, model_id, inputs):
        response = self.fetch(f"/models/{model_id}", payload=inputs, method="post")
        if response:
            return response["data"]
        return None

    def embed(self, inputs: List[str], model_id="intfloat/e5-base-v2") -> List[List[float]]:
        batch_size = 100
        embeddings = []
        try:
            for i in range(0, len(inputs), batch_size):
                i_end = min(len(inputs), i+batch_size)
                batch = inputs[i:i_end]
                payload = { "input": [ text.replace("\n", " ") for text in batch ], "model": model_id }
                response = self.fetch(f"/embeddings", payload=payload, method="post")
                embeddings += [d["embedding"] for d in response["data"]]
        except:
            return None
        return embeddings

    def textreader(self, file: str):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        url = f"/textprocessing/textreader"
        file_ = {"file": open(file, "rb")}
        return self.fetch(url, files=file_, method="post")
    
    def vectorize_file(self, file: str, chunk_size: int = 256, chunk_overlap: int = 50, meta: dict = {}, embeddings=True):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        url = f"/textprocessing/vectorizefile?chunk_size={chunk_size}&chunk_overlap={chunk_overlap}"
        if meta:
            url = url + "&meta=" + json.dumps(meta)
        file_ = {"file": open(file, "rb")}
        response = self.fetch(url, files=file_, method="post")
        if embeddings and "data" in response:
            chunks = [d["chunk"] for d in response["data"]]
            e = self.embed(chunks)
            for i, _ in enumerate(e):
                response["data"][i]["embedding"] = e[i]
        return response
