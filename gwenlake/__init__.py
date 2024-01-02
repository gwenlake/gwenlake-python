"""Gwenlake API Client."""
import os
from importlib import metadata

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available.
    __version__ = ""


from gwenlake.client import Client

__all__ = [
    "__version__",
    "Client",
]

api_key  = os.environ.get("GWENLAKE_API_KEY")
api_base = os.environ.get("GWENLAKE_API_BASE") or "https://api.gwenlake.com/v1"

