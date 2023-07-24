import requests
from typing import Optional

import gwenlake


class Client:

    def __init__(self, api_key: Optional[str] = None, organization: Optional[str] = None):
        self.api_key = api_key or gwenlake.api_key
        self.organization = organization or gwenlake.organization
        self.api_base = gwenlake.api_base
        self.timeout = gwenlake.TIMEOUT
        self.headers = { "Authorization": f"Bearer {self.api_key}"}
        self.session = requests.Session()


    def _build_api_url(self, query):
        return f"{self.api_base}/{query}"
    

    def _post(self, query, payload):
        resp = self.session.post(
            self._build_api_url(query),
            headers=self.headers,
            timeout=self.timeout,
            json=payload,
        )
        return resp