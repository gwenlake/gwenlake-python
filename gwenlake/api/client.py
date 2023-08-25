import os
import requests
from typing import Optional

from ..constants import ENDPOINT


class APIClient:

    def __init__(self, token: Optional[str] = None, endpoint: Optional[str] = None):
        self.token = token or os.environ.get("GWENLAKE_API_KEY")
        self.endpoint = endpoint or ENDPOINT
        self.headers = { "Authorization": f"Bearer {self.token}"}
        self.session = requests.Session()
    
    def fetch(self, query, payload: Optional[str] = None, method: Optional[str] = "get"):
        url = f"{self.endpoint}{query}"
        if method == "post":
            resp = self.session.post(url, headers=self.headers, json=payload)
        else:
            resp = self.session.get(url, headers=self.headers, json=payload)
        if resp.status_code == 200:
            return resp.json()
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
    
    def embed_documents(self, documents, model_id="all-mpnet-base-v2"):
        payload = [ { "input": text } for text in documents ]
        resp = self.fetch(f"/models/{model_id}", payload=payload, method="post")
        if resp:
            if "data" in resp:
                return [x["embedding"] for x in resp["data"]]
        return None