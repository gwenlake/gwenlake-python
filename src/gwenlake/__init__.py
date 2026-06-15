import importlib.metadata

__version__ = importlib.metadata.version(__package__)

from gwenlake.credentials import Credentials  # noqa
from gwenlake.client import Gwenlake, AsyncGwenlake  # noqa
