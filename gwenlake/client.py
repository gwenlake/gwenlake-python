import os
import logging
import requests
from typing import Optional


ENDPOINT = "https://api.gwenlake.com/v1"

logger = logging.getLogger(__name__)


class Client:

    def __init__(self, token: Optional[str] = None, endpoint: Optional[str] = None, timeout: Optional[int] = 20):
        self.token = token or os.environ.get("GWENLAKE_API_KEY")
        self.api_url = endpoint or ENDPOINT
        self.headers = { "Authorization": f"Bearer {self.token}"}
        self.session = requests.Session()
        self.timeout = timeout
    
    
    def fetch(self, query, payload: Optional[str] = None, files: Optional[dict] = None, method: Optional[str] = "get"):
        url = f"{self.api_url}{query}"
        if method == "post":
            if files:
                resp = self.session.post(url, headers=self.headers, json=payload, files=files, timeout= self.timeout)
            else:
                resp = self.session.post(url, headers=self.headers, json=payload, timeout= self.timeout)
        else:
            resp = self.session.get(url, headers=self.headers, json=payload, timeout= self.timeout)
        if resp.status_code != 200:
            raise Exception
        return resp.json()