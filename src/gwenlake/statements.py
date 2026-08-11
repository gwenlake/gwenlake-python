from typing import Any, Dict, Optional, Union

from gwenlake.client import ApiClient, AsyncApiClient, RequestOptions


# What each `format` sends back, so `Accept` matches what the server will
# actually return (`pyarrow` is an Arrow IPC *file*, not JSON).
_ACCEPT_BY_FORMAT = {
    "json": "application/json",
    "csv": "text/csv",
    "pyarrow": "application/vnd.apache.arrow.file",
}


def _payload(statement, connection_id, format, parameters, limit) -> dict:
    payload: Dict[str, Any] = {"statement": statement, "format": format}
    if connection_id:
        payload["connection_id"] = connection_id
    if parameters:
        payload["parameters"] = parameters
    if limit:
        payload["limit"] = limit
    return payload


def _options(statement, connection_id, format, parameters, limit, timeout) -> RequestOptions:
    return RequestOptions(
        method="POST",
        url="/sql/statements",
        headers={
            "Accept": _ACCEPT_BY_FORMAT.get(format, "application/json"),
            "Content-Type": "application/json",
        },
        json_data=_payload(statement, connection_id, format, parameters, limit),
        timeout=timeout,
    )


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
        timeout: Optional[float] = None,
    ) -> Union[Dict[str, Any], bytes]:
        """Run a SQL statement. Without ``connection_id`` it runs in dataset
        mode and must reference ``FROM '<project>.<dataset>'``. ``format="json"``
        returns ``{"object": "list", "data": [...]}``; other formats (``csv``,
        ``pyarrow``) return raw bytes.

        ``timeout`` overrides the client's default for this call — a scan over a
        large dataset can take far longer to answer than an ordinary request."""
        response = self._client.send(
            _options(statement, connection_id, format, parameters, limit, timeout),
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
        timeout: Optional[float] = None,
    ) -> Union[Dict[str, Any], bytes]:
        response = await self._client.send(
            _options(statement, connection_id, format, parameters, limit, timeout),
        )
        response.raise_for_status()
        return response.json() if format == "json" else response.content
