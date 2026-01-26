import time
from typing import Any, Optional, Dict
from pydantic import BaseModel


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: Optional[str] = "Bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None

    def __init__(self, token_response: Dict[str, Any]) -> None:
        super().__init__(**token_response)

    @classmethod
    def from_token(cls, token: str):
        return cls(
            token_response=dict(access_token=token),
        )

class OAuthToken:
    def __init__(self, token: OAuthTokenResponse):
        self._token = token

    @property
    def access_token(self) -> str:
        return self._token.access_token

    @property
    def refresh_token(self) -> Optional[str]:
        return self._token.refresh_token

    @property
    def expires_in(self) -> int:
        return self._token.expires_in

    @property
    def token_type(self) -> str:
        return self._token.token_type

    def _calculate_expiration(self) -> int:
        return int(self._token.expires_in * 1000 + self.current_time())

    @property
    def expires_at(self) -> int:
        return self._calculate_expiration()

    @staticmethod
    def current_time() -> int:
        return int(time.time() * 1000)
