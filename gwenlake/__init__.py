import os

from gwenlake.api import (
    Client,
)

from gwenlake.version import VERSION

api_key      = os.environ.get("GWENLAKE_API_KEY")
organization = os.environ.get("GWENLAKE_ORGANIZATION")
api_base     = os.environ.get("GWENLAKE_API_BASE", "https://api.gwenlake.com/v1")
TIMEOUT      = 500

__version__ = VERSION
