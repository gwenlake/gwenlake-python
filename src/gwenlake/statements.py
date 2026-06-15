from typing import Any, Dict, Optional, Union

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions


def _payload(statement, connection_id, format, parameters, limit) -> dict:
    payload: Dict[str, Any] = {"statement": statement, "format": format}
    if connection_id:
        payload["connection_id"] = connection_id
    if parameters:
        payload["parameters"] = parameters
    if limit:
        payload["limit"] = limit
    return payload


class Statements:

    def __init__(self, client: ApiClient):
        self._client = client

    def create(
        self,
        *,
        statement: str,
        connection_id: Optional[str] = None,
        format: str = "json",
        parameters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Union[Dict[str, Any], bytes]:
        """Run a SQL statement. Without ``connection_id`` it runs in dataset
        mode and must reference ``FROM '<project>.<dataset>'``. ``format="json"``
        returns ``{"object": "list", "data": [...]}``; other formats (``csv``,
        ``pyarrow``) return raw bytes."""
        response = self._client.send(
            RequestOptions(
                method="POST",
                url="/sql/statements",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json_data=_payload(statement, connection_id, format, parameters, limit),
            ),
        )
        response.raise_for_status()
        return response.json() if format == "json" else response.content


class AsyncStatements:

    def __init__(self, client: AsyncApiClient):
        self._client = client

    async def create(
        self,
        *,
        statement: str,
        connection_id: Optional[str] = None,
        format: str = "json",
        parameters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Union[Dict[str, Any], bytes]:
        response = await self._client.send(
            RequestOptions(
                method="POST",
                url="/sql/statements",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json_data=_payload(statement, connection_id, format, parameters, limit),
            ),
        )
        response.raise_for_status()
        return response.json() if format == "json" else response.content
