import importlib.metadata

__version__ = importlib.metadata.version(__package__)

from gwenlake.client.main import Client  # noqa
