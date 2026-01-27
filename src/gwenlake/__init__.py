import importlib.metadata

__version__ = importlib.metadata.version(__package__)

from gwenlake.auth.credentials import Credentials  # noqa
from gwenlake.inference.client import InferenceClient  # noqa
from gwenlake.factory.client import FactoryClient  # noqa
