import httpx
from typing import Optional



class HttpClient(httpx.Client):
    def __init__(self, hostname: str, verify: Optional[bool] = True, timeout: Optional[int] = None, scheme: Optional[str] = "https"):

        self._verify = verify

        super().__init__(
            follow_redirects=True,
            base_url=f"{scheme}://{hostname}",
            timeout=timeout,
        )


class AsyncHttpClient(httpx.AsyncClient):
    def __init__(self, hostname: str, verify: Optional[bool] = True, timeout: Optional[int] = None, scheme: Optional[str] = "https"):

        self._verify = verify

        super().__init__(
            follow_redirects=True,
            base_url=f"{scheme}://{hostname}",
            timeout=timeout,
        )
