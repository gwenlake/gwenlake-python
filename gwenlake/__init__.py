"""Gwenlake API Client."""
from importlib import metadata

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available.
    __version__ = ""

from gwenlake.client import Client

__all__ = [
    "Client",
    "__version__",
]