import httpx

DEFAULT_TIMEOUT = httpx.Timeout(timeout=120.0, connect=5.0)
