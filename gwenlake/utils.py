"""Generic utility functions."""
import enum
import functools
import logging
import os
import subprocess
from typing import Any, Callable, Dict, List, Mapping, Tuple, Union

import requests

from gwenlake import schemas as glk_schemas


_LOGGER = logging.getLogger(__name__)


class GwenlakeAPIError(Exception):
    """An error occurred while communicating with the Gwenlake API."""


class GwenlakeUserError(Exception):
    """An error occurred while communicating with the Gwenlake API."""


class GwenlakeError(Exception):
    """An error occurred while communicating with the Gwenlake API."""


class GwenlakeConnectionError(Exception):
    """Couldn't connect to the Gwenlake API."""


def tracing_is_enabled() -> bool:
    """Return True if tracing is enabled."""
    return (
        os.environ.get(
            "LANGCHAIN_TRACING_V2", os.environ.get("LANGCHAIN_TRACING", "")
        ).lower()
        == "true"
    )


def raise_for_status_with_text(response: requests.Response) -> None:
    """Raise an error with the response text."""
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise ValueError(str(e), response.text) from e


def get_enum_value(enu: Union[enum.Enum, str]) -> str:
    """Get the value of a string enum."""
    if isinstance(enu, enum.Enum):
        return enu.value
    return enu

