from __future__ import annotations

from typing import Optional


class GwenlakeException(Exception):
    """A base class for all Gwenlake exceptions."""

    def __init__(self, message: Optional[str] = None) -> None:
        super(GwenlakeException, self).__init__(message)

        self.message = message

    def __str__(self) -> str:
        msg = self.message or "<empty message>"
        return msg

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={str(self)})"
    

class GwenlakeError(GwenlakeException):
    """An error from Gwenlake."""

