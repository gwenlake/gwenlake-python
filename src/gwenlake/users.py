"""`/users/me` — who the credentials belong to, and their plans."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Users(Resource):

    def me(self) -> Dict[str, Any]:
        return self._json("GET", "/users/me")

    def plans(self) -> Any:
        return self._json("GET", "/users/me/plans")

class AsyncUsers(AsyncResource):

    async def me(self) -> Dict[str, Any]:
        return await self._json("GET", "/users/me")

    async def plans(self) -> Any:
        return await self._json("GET", "/users/me/plans")
