import os
import sys
from typing import TYPE_CHECKING, Optional, Union, Callable

from contextvars import ContextVar

if "pkg_resources" not in sys.modules:
    # workaround for the following:
    # https://github.com/benoitc/gunicorn/pull/2539
    sys.modules["pkg_resources"] = object()  # type: ignore[assignment]
    import aiohttp
    del sys.modules["pkg_resources"]


from openai.version import VERSION

if TYPE_CHECKING:
    import requests
    from aiohttp import ClientSession


api_key      = os.environ.get("GWENLAKE_API_KEY")
organization = os.environ.get("GWENLAKE_ORGANIZATION")
api_base     = "https://api.gwenlake.com/v1"
api_version  = VERSION




requestssession: Optional[
    Union["requests.Session", Callable[[], "requests.Session"]]
] = None # Provide a requests.Session or Session factory.

aiosession: ContextVar[Optional["ClientSession"]] = ContextVar(
    "aiohttp-session", default=None
)  # Acts as a global aiohttp ClientSession that reuses connections.
# This is user-supplied; otherwise, a session is remade for each request.
