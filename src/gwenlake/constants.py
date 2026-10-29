import httpx

# default timeout is 1 minute
DEFAULT_TIMEOUT = httpx.Timeout(timeout=60, connect=5.0)
DEFAULT_MAX_RETRIES = 2
DEFAULT_CONNECTION_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)

INITIAL_RETRY_DELAY = 0.5
MAX_RETRY_DELAY = 8.0

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

#: The public API gateway: the Gwenlake APIs and the Atlas catalog under /v1.
GWENLAKE_API_URL = "https://api.gwenlake.com/v1"

#: The same API as the Atlas application serves it, under /api/v1.
GWENLAKE_ATLAS_URL = "https://atlas.gwenlake.com/api/v1"

#: Short names accepted wherever an endpoint is given (`base_url=`,
#: `--base-url`, `GWENLAKE_BASE_URL`, a profile's `base_url`). A tenant
#: deployed on its own host is given as that host: `atlas.acme.example`.
KNOWN_ENDPOINTS = {
    "api": GWENLAKE_API_URL,
    "atlas": GWENLAKE_ATLAS_URL,
}

#: What a client uses when nothing names an endpoint.
DEFAULT_BASE_URL = GWENLAKE_API_URL
