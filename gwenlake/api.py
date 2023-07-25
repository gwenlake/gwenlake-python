import requests
from typing import Optional

import gwenlake


class Client:

    def __init__(self, token: Optional[str] = None, organization: Optional[str] = None):
        self.token = token or gwenlake.api_key
        self.organization = organization or gwenlake.organization
        self.api_base = gwenlake.api_base
        self.timeout = gwenlake.timeout
        self.headers = { "Authorization": f"Bearer {self.token}"}
        self.session = requests.Session()


    def _build_api_url(self, query):
        return f"{self.api_base}/{query}"
    

    def _post(self, query, payload: Optional[str] = None):
        resp = self.session.post(
            self._build_api_url(query),
            headers=self.headers,
            timeout=self.timeout,
            json=payload,
        )
        return resp

    def _get(self, query, payload: Optional[str] = None):
        resp = self.session.get(
            self._build_api_url(query),
            headers=self.headers,
            timeout=self.timeout,
            json=payload,
        )
        return resp

    def list_models(self):
        resp = self._get("models")
        if resp.status_code == 200:
            return resp.json()["data"]
        return None
