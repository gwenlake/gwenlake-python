import logging
import requests
import json
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
        print(self.api_key)
        headers = { "Authorization": f"Bearer {self.api_key}", "Accept": "application/json" }
        if method == "post":
            # data_to_send = json.dumps(payload).encode("utf-8")
            # r = self.session.post(url, headers=headers, data=data_to_send, timeout=self.timeout, files=files)
            r = self.session.post(url, headers=headers, json=payload, timeout=self.timeout, files=files)
            print(r)
        else:
            r = self.session.get(url, headers=headers, json=payload, timeout=self.timeout)
        if r.status_code != 200:
            # logger.exception("An error occurred while embedding.")
            raise Exception
        return r.json()