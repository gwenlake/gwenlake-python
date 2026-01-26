import os
import configparser
import threading
import logging
import httpx
from typing import Any, List, Optional, Dict
from pydantic import BaseModel

from gwenlake.core.flow import ClientOAuthFlowProvider
from gwenlake.core.token import OAuthToken, OAuthTokenResponse
# from gwenlake.core.profile import load_user_profile


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

        self._client: Optional[HttpClient] = None
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
    
    @classmethod
    def from_profile(cls, profile: str = "default"):
        try:                
            config_path = None

            if os.name == "nt":
                config_path = os.getenv("APPDATA")
            if not config_path:
                config_path = os.path.expanduser("~")

            config_path = os.path.join(config_path, GWENLAKE_PROFILES, "credentials")

            _config = configparser.ConfigParser()
            _config.read(config_path)

            info = _config[profile]

            hostname = info.get("hostname")
            token_uri = None
            if hostname:
                token_uri = f"{hostname}" + TOKEN_REQUEST_PATH
                        
            return cls(
                token=info.get("token"),
                hostname=hostname,
                token_uri=token_uri,
                client_id=info.get("client_id"),
                client_secret=info.get("client_secret"),
                scopes = info.get("scopes"),
            )
    
        except (IOError, ValueError) as e:
            logger.debug(
                "Error loading credentials from {}: {}".format(config_path, str(e))
            )

    # def save_profile(self, name: str, profile: Profile):
    #     config_path = _get_default_user_profile_path()

    #     config_dir = os.path.dirname(config_path)
    #     if not os.path.exists(config_dir):
    #         try:
    #             os.makedirs(config_dir)
    #         except OSError as exc:
    #             if exc.errno != errno.EEXIST:
    #                 logger.warning(f"Unable to create {_DIRNAME} directory.")
    #                 return

    #     config = configparser.ConfigParser()

    #     if os.path.exists(config_path):
    #         try:
    #             config.read(config_path)
    #         except (IOError, ValueError) as exc:
    #             logger.debug(
    #                 "Error loading credentials from {}: {}".format(
    #                     config_path, str(exc)
    #                 )
    #             )

    #     if name != "default" and not config.has_section(name):
    #         config.add_section(name)

    #     config[name]["token"] = profile.token
    #     config[name]["client_id"] = profile.client_id
    #     config[name]["client_secret"] = profile.client_secret
    #     if profile.scopes is not None:
    #         config[name]["scopes"] = ",".join(profile.scopes)
    #     config[name]["tenant"] = profile.tenant

    #     try:
    #         with open(config_path, "w") as f:
    #             config.write(f)
    #     except IOError:
    #         logger.warning("Unable to save profile.")