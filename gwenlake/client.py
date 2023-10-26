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
    