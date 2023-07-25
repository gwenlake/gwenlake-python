import os
import requests
from typing import Optional

from .constants import ENDPOINT


class Client:

    def __init__(self, token: Optional[str] = None, endpoint: Optional[str] = None):
        self.token = token or os.environ.get("GWENLAKE_API_KEY")
        self.endpoint = endpoint or ENDPOINT
        self.headers = { "Authorization": f"Bearer {self.token}"}
        self.session = requests.Session()


    def _build_api_url(self, query):
        return f"{self.endpoint}/{query}"
    

    def _call(self, query, payload: Optional[str] = None, method: Optional[str] = "get"):
        url = self._build_api_url(query)
        if method == "post":
            resp = self.session.post(url, headers=self.headers, json=payload)
        else:
            resp = self.session.get(url, headers=self.headers, json=payload)
        if resp.status_code == 200:
            return resp.json()
        return None

    def list_models(self):
        resp = self._call("models")
        if resp:
            return resp["data"]
        return None
