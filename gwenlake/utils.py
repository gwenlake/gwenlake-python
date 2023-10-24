import enum
import logging
import os
from typing import Any, Callable, Dict, List, Mapping, Tuple, Union
import tiktoken

# import requests
# from gwenlake import schemas as glk_schemas


_LOGGER = logging.getLogger(__name__)


class GwenlakeAPIError(Exception):
    """An error occurred while communicating with the Gwenlake API."""


class GwenlakeUserError(Exception):
    """An error occurred while communicating with the Gwenlake API."""


class GwenlakeError(Exception):
    """An error occurred while communicating with the Gwenlake API."""


class GwenlakeConnectionError(Exception):
    """Couldn't connect to the Gwenlake API."""


def langchain_tracing_is_enabled() -> bool:
    """Return True if tracing is enabled."""
    return (
        os.environ.get(
            "LANGCHAIN_TRACING_V2", os.environ.get("LANGCHAIN_TRACING", "")
        ).lower()
        == "true"
    )

def get_enum_value(enu: Union[enum.Enum, str]) -> str:
    """Get the value of a string enum."""
    if isinstance(enu, enum.Enum):
        return enu.value
    return enu

def num_tokens_from_string(string: str, encoding_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens
