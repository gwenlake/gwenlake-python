import os
import configparser
import threading
import logging
import httpx
from typing import Any, List, Optional, Dict
from pydantic import BaseModel

from gwenlake.flow import ClientOAuthFlowProvider
from gwenlake.token import OAuthToken, OAuthTokenResponse


GWENLAKE_PROFILES = ".gwenlake"
TOKEN_REQUEST_PATH = "/protocol/openid-connect/token"


logger = logging.getLogger(__name__)


class SignInResponse(BaseModel):
    session: Dict[str, Any]

class SignOutResponse(BaseModel):
    pass


class Credentials:

    def __init__(
        self,
        *,
        token: Optional[str] = None,
        token_uri: Optional[str] = None,
        hostname: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        should_refresh: bool = True,
    ):
        
        self._token = OAuthToken(token=OAuthTokenResponse.from_token(token)) if token else None
        self._hostname = hostname
        self._token_uri = token_uri
        self._client_id = client_id
        self._client_secret = client_secret
        self._scopes = scopes
        
        if self._scopes is not None:
            if not isinstance(self._scopes, list):
                raise TypeError(f"The scopes must be a list, not {type(self._scopes)}.")

        self._client: Optional[httpx.Client] = None
        self._should_refresh = should_refresh
        self._stop_refresh_event = threading.Event()
        self._server_oauth_flow_provider = None

        if self._client_id and self._client_secret:
            self._server_oauth_flow_provider = ClientOAuthFlowProvider(
                client_id=self._client_id,
                client_secret=self._client_secret,
                scopes=self._scopes,
            )

    @property
    def token(self) -> str:
        return self._token.access_token
    
    @property
    def hostname(self) -> str:
        return self._hostname

    @property
    def token_uri(self) -> str:
        return self._token_uri

    @property
    def scopes(self) -> List[str]:
        if not self._server_oauth_flow_provider:
            return self._scopes or []
        return self._server_oauth_flow_provider.scopes or []

    @property
    def url(self) -> str:
        return self._get_oauth_client().base_url.host

    @property
    def is_configured(self) -> bool:
        """True when these credentials can produce a token (static token or OAuth2)."""
        return self._token is not None or self._server_oauth_flow_provider is not None

    def sign_out(self) -> SignOutResponse:
        self._revoke_token()
        self._token = None
        self._stop_refresh_event.set()
        return SignOutResponse()

    def get_token(self) -> OAuthToken:
        if self._token is None and self._server_oauth_flow_provider:
            self._token = self._server_oauth_flow_provider.get_token(self._get_oauth_client())

            if self._should_refresh:
                self._start_auto_refresh()

        return self._token

    def _revoke_token(self) -> None:
        if self._token and self._server_oauth_flow_provider:
            self._server_oauth_flow_provider.revoke_token(
                self._get_oauth_client(),
                self._token.access_token,
            )

    def _try_refresh_token(self) -> bool:
        if self._server_oauth_flow_provider:
            self._token = self._server_oauth_flow_provider.get_token(self._get_oauth_client())
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

    def _get_oauth_client(self) -> httpx.Client:
        if self._client is None:
            if self._hostname:
                self._client = httpx.Client(base_url=self._token_uri)
        return self._client
    
    @staticmethod
    def _default_config_path() -> str:
        base = os.getenv("APPDATA") if os.name == "nt" else None
        if not base:
            base = os.path.expanduser("~")
        return os.path.join(base, GWENLAKE_PROFILES, "credentials")

    @classmethod
    def from_profile(cls, profile: str = "default") -> Optional["Credentials"]:
        """Load credentials from the ``~/.gwenlake/credentials`` INI file.

        Each section is a named profile and may hold either a static ``token``
        (API key) or OAuth2 ``client_id``/``client_secret`` settings. Returns
        ``None`` when the file or the requested profile does not exist.
        """
        config_path = cls._default_config_path()

        config = configparser.ConfigParser()
        try:
            read = config.read(config_path)
        except (IOError, configparser.Error) as e:
            logger.debug("Error loading credentials from %s: %s", config_path, e)
            return None

        if not read or not config.has_section(profile):
            logger.debug("Profile '%s' not found in %s", profile, config_path)
            return None

        info = config[profile]

        hostname = info.get("hostname")
        token_uri = f"{hostname}{TOKEN_REQUEST_PATH}" if hostname else None

        scopes = info.get("scopes")
        if scopes:
            scopes = [s.strip() for s in scopes.split(",") if s.strip()]

        return cls(
            token=info.get("token"),
            hostname=hostname,
            token_uri=token_uri,
            client_id=info.get("client_id"),
            client_secret=info.get("client_secret"),
            scopes=scopes,
        )