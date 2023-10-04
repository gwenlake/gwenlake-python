import logging
import requests
from typing import Optional

import gwenlake


TIMEOUT  = 20

logger = logging.getLogger(__name__)


class Client:

    def __init__(self, api_key: Optional[str] = None, api_base: Optional[str] = None, timeout: Optional[float] = TIMEOUT):
        self.api_key  = api_key or gwenlake.api_key
        self.api_base = api_base or gwenlake.api_base
        self.timeout  = timeout
        self.session  = requests.Session()
    
    
    def fetch(self, query, payload: Optional[str] = None, files: Optional[dict] = None, method: Optional[str] = "get"):
        url = f"{self.api_base}{query}"
        headers = { "Authorization": f"Bearer {self.api_key}" }
        if method == "post":
            resp = self.session.post(url, headers=headers, json=payload, timeout=self.timeout, files=files)
        else:
            resp = self.session.get(url, headers=headers, json=payload, timeout=self.timeout)
        if resp.status_code != 200:
            raise Exception
        return resp.json()