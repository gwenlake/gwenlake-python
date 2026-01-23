import threading
from typing import Any, List, Optional, Dict
from pydantic import BaseModel

from gwenlake.factory.core.httpclient import HttpClient
from gwenlake.factory.core.flow import ClientOAuthFlowProvider, OAuthUtils
from gwenlake.factory.core.token import OAuthToken
from gwenlake.factory.core.profile import load_user_profile


class SignInResponse(BaseModel):
    session: Dict[str, Any]

class SignOutResponse(BaseModel):
    pass


class Credentials:

    def __init__(
        self,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        hostname: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        should_refresh: bool = True,
        profile: Optional[str] = None,
    ) -> None:
        
        self._hostname = hostname
        self._client: Optional[HttpClient] = None
        self._should_refresh = should_refresh
        self._stop_refresh_event = threading.Event()
        self._token: Optional[OAuthToken] = None

        self._client_id = client_id
        self._client_secret = client_secret
        self._scopes = scopes

        if self._client_id is None:
            _profile = load_user_profile(profile)
            self._hostname = _profile.hostname
            self._client_id = _profile.client_id
            self._client_secret = _profile.client_secret
            self._scopes = _profile.scopes

        if self._scopes is not None:
            if not isinstance(self._scopes, list):
                raise TypeError(f"The scopes must be a list, not {type(self._scopes)}.")

        self._server_oauth_flow_provider = ClientOAuthFlowProvider(
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=self._scopes,
        )

    @property
    def hostname(self) -> str:
        return self._hostname

    def sign_out(self) -> SignOutResponse:
        self._revoke_token()
        self._token = None
        self._stop_refresh_event.set()
        return SignOutResponse()
    
    @property
    def scopes(self) -> List[str]:
        return self._server_oauth_flow_provider.scopes or []

    def get_token(self) -> OAuthToken:
        if self._token is None:
            self._token = self._server_oauth_flow_provider.get_token(self._get_client())

            if self._should_refresh:
                self._start_auto_refresh()

        return self._token

    def _revoke_token(self) -> None:
        if self._token:
            self._server_oauth_flow_provider.revoke_token(
                self._get_client(),
                self._token.access_token,
            )

    @property
    def url(self) -> str:
        return self._get_client().base_url.host

    def _try_refresh_token(self) -> bool:
        self._token = self._server_oauth_flow_provider.get_token(self._get_client())
        return True


    def _start_auto_refresh(self) -> None:
        def _auto_refresh_token() -> None:
            while True:
                timeout = self._token.expires_in - 60 if self._token else 10
                if self._stop_refresh_event.wait(timeout):
                    return
                if self._token:
                    self._try_refresh_token()

        refresh_thread = threading.Thread(target=_auto_refresh_token, daemon=True)
        refresh_thread.start()

    def _get_client(self) -> HttpClient:
        if self._client is None:
            # self._client = HttpClient(hostname=self._hostname)
            self._client = HttpClient(hostname=OAuthUtils.base_hostname)

        return self._client
