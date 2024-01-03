from __future__ import annotations

from typing import TYPE_CHECKING

from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Data"]



class Data(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)

    def push(
        self,
        *,
        ref: str,
        data: dict,
    ):
        # TODO: url = f"/data/{ data_id }/uploaddata" and replace by PUT
        resp = self._client._request("POST", f"/data/{ ref }", json=data)

        resp.raise_for_status()

        return f"/data/{ ref }"
