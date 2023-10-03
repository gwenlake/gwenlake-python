import io
import os
import logging
import requests
from typing import Optional, Union, Sequence, Tuple


ENDPOINT = "https://api.gwenlake.com/v1"


logger = logging.getLogger(__name__)


class Client:

    def __init__(self, token: Optional[str] = None, endpoint: Optional[str] = None, timeout: Optional[int] = None,):
        self.token = token or os.environ.get("GWENLAKE_API_KEY")
        self.api_url = endpoint or ENDPOINT
        self.headers = { "Authorization": f"Bearer {self.token}"}
        self.session = requests.Session()
        self.timeout = timeout or 15
    
    
    def fetch(self, query, payload: Optional[str] = None, files: Optional[dict] = None, method: Optional[str] = "get"):
        url = f"{self.api_url}{query}"
        if method == "post":
            if files:
                resp = self.session.post(url, headers=self.headers, json=payload, files=files, timeout= self.timeout)
            else:
                resp = self.session.post(url, headers=self.headers, json=payload, timeout= self.timeout)
        else:
            resp = self.session.get(url, headers=self.headers, json=payload, timeout= self.timeout)
        if resp.status_code == 200:
            return resp.json()
        return None


    def upload_file(self, file: Union[str, Tuple[str, io.BytesIO]]):

        if isinstance(file, str):
            with open(file, "rb") as f:
                file_ = {"file": f}
                response = self.session.post(
                    self.api_url + "/data/upload",
                    headers=self.headers,
                    files=file_,
                )
        elif isinstance(file, tuple):
            file_ = {"file": file}
            response = self.session.post(
                self.api_url + "/data/upload",
                headers=self.headers,
                files=file_,
            )
        else:
            raise ValueError("file must be a string or tuple")
    
        if response.status_code == 200:
            result = response.json()
            if "detail" in result and "already exists" in result["detail"]:
                file_name = file if isinstance(file, str) else file[0]
                file_name = file_name.split("/")[-1]
                raise ValueError(f"Dataset {file_name} already exists")
            return result

        return None


    def list_models(self):
        resp = self.fetch("/models")
        if resp:
            return resp["data"]
        return None

    def model(self, model_id, payload):
        resp = self.fetch(f"/models/{model_id}", payload=payload, method="post")
        if resp:
            return resp["data"]
        return None
    
    def embed_documents(self, documents, model_id="e5-base-v2"):
        payload = [ { "input": text } for text in documents ]
        resp = self.fetch(f"/models/{model_id}", payload=payload, method="post")
        if resp:
            if "data" in resp:
                return [x["embedding"] for x in resp["data"]]
        return None