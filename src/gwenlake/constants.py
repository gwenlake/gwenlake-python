import re

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

#: The Gwenlake API: inference and the Atlas catalog, all served by Atlas
#: under /api/v1.
GWENLAKE_ATLAS_URL = "https://atlas.gwenlake.com/api/v1"

#: Kept for the code that imported it: the same endpoint.
GWENLAKE_API_URL = GWENLAKE_ATLAS_URL

#: The endpoint of a tenant, from its name: a profile's `host` / `hostname`
#: (or `base_url=acme`, `--base-url acme`) is `https://acme.gwenlakeatlas.com/api/v1`.
GWENLAKE_TENANT_URL = "https://{tenant}.gwenlakeatlas.com/api/v1"

#: What a tenant name looks like: one DNS label, no dot, no scheme, no port.
#: Anything else given as an endpoint is a host or a URL.
TENANT_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?")

#: Short names accepted wherever an endpoint is given (`base_url=`,
#: `--base-url`, `GWENLAKE_BASE_URL`, a profile's `base_url`). Any other bare
#: name is a tenant (`GWENLAKE_TENANT_URL`); a full host or URL is kept.
KNOWN_ENDPOINTS = {
    "atlas": GWENLAKE_ATLAS_URL,
    "api": GWENLAKE_ATLAS_URL,
}

#: What a client uses when nothing names an endpoint.
DEFAULT_BASE_URL = GWENLAKE_ATLAS_URL
