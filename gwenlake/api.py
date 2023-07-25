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
    

    def _post(self, query, payload: Optional[str] = None):
        resp = self.session.post(
            self._build_api_url(query),
            headers=self.headers,
            json=payload,
        )
        return resp

    def _get(self, query, payload: Optional[str] = None):
        resp = self.session.get(
            self._build_api_url(query),
            headers=self.headers,
            json=payload,
        )
        return resp

    def list_models(self):
        resp = self._get("models")
        if resp.status_code == 200:
            return resp.json()["data"]
        return None
