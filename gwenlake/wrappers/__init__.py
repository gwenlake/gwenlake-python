"""Gwenlake API Client."""
import os
from importlib import metadata

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available.
    __version__ = ""

from gwenlake.client import Client
from gwenlake.embeddings import get_embeddings


__all__ = [
    "Client",
    "__version__",
    "get_embeddings",
]

api_key  = os.environ.get("GWENLAKE_API_KEY")
api_base = os.environ.get("GWENLAKE_API_BASE") or "https://api.gwenlake.com/v1"

