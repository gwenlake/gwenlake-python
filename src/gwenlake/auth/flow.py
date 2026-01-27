import httpx
from typing import List, Optional

from gwenlake.auth.token import OAuthToken, OAuthTokenResponse


class OAuthUtils:
    base_hostname = "auth.gwenlake.com"
    base_context_path = "/realms/gwenlake-api"
    authorize_request_path = "/authz/protection/permission"
    token_request_path = "/protocol/openid-connect/token"

    @staticmethod
    def get_token_uri(context_path: Optional[str] = None) -> str:
        return OAuthUtils.create_uri(context_path, OAuthUtils.token_request_path)

    @staticmethod
    def get_authorize_uri(context_path: Optional[str] = None) -> str:
        return OAuthUtils.create_uri(context_path, OAuthUtils.authorize_request_path)

    @staticmethod
    def create_uri(context_path: Optional[str], request_path: str) -> str:
        return (context_path or OAuthUtils.base_context_path) + request_path


class ClientOAuthFlowProvider:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        auth_context_path: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self.auth_context_path = auth_context_path
        self.scopes = scopes

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def client_secret(self) -> str:
        return self._client_secret

    def get_token(self, client: httpx.Client) -> OAuthToken:
        params = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }
        scopes = self.get_scopes()
        if len(scopes) > 0:
            params["scope"] = " ".join(scopes)

        token_url = OAuthUtils.get_token_uri(self.auth_context_path)
        response = client.post(token_url, data=params)
        response.raise_for_status()
        return OAuthToken(token=OAuthTokenResponse(token_response=response.json()))

    def revoke_token(self, client: httpx.Client, access_token: str) -> None:
        body = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "token": access_token,
        }

        token_url = OAuthUtils.get_revoke_uri(self.auth_context_path)
        revoke_token_response = client.post(token_url, data=body)
        revoke_token_response.raise_for_status()

    def get_scopes(self) -> List[str]:
        if not self.scopes:
            return []
        return [*self.scopes, "offline_access"]

