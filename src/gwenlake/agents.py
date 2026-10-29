"""`/agents` — the project's conversational agents: a model, instructions and
tools, versioned; `start_session` / `continue_session` talk to one."""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


class Agents(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/agents", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, agent_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/agents/{agent_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `model`, `instructions`, `tools`, `chat`."""
        return self._json("POST", "/agents", json=data)

    def update(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("PATCH", f"/agents/{agent_id}", json=data)

    def delete(self, agent_id: str) -> bool:
        return self._ok("DELETE", f"/agents/{agent_id}")

    def restore(self, agent_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/agents/{agent_id}/restore")

    def versions(self, agent_id: str, *, limit: Optional[int] = None, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/agents/{agent_id}/versions", params={"limit": limit, "branch": branch})

    def version(self, agent_id: str, version_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return self._json("GET", f"/agents/{agent_id}/versions/{version_id}", params={"branch": branch})

    def tool_registry(self) -> List[Dict[str, Any]]:
        """Every tool an agent may be given."""
        return self._list("GET", "/agents/tools")

    def tools(self, agent_id: str, *, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", f"/agents/{agent_id}/tools", params={"branch": branch})

    def invoke_tool(self, agent_id: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None, *, branch: Optional[str] = None) -> Any:
        return self._json("POST", f"/agents/{agent_id}/tools/{tool_name}/invoke", json={"arguments": arguments or {}}, params={"branch": branch})

    def sessions(self, agent_id: str) -> List[Dict[str, Any]]:
        return self._list("GET", f"/agents/{agent_id}/sessions")

    def session(self, agent_id: str, session_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/agents/{agent_id}/sessions/{session_id}")

    def start_session(self, agent_id: str, input: Any, *, model: Optional[str] = None, temperature: Optional[float] = None, timeout: Optional[float] = None, branch: Optional[str] = None) -> Dict[str, Any]:
        """Open a conversation with the agent; answers the session and its first reply."""
        return self._json("POST", f"/agents/{agent_id}/sessions", json={k: v for k, v in {"input": input, "model": model, "temperature": temperature, "timeout": timeout}.items() if v is not None}, params={"branch": branch}, timeout=timeout)

    def continue_session(self, agent_id: str, session_id: str, input: Any, *, model: Optional[str] = None, temperature: Optional[float] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self._json("POST", f"/agents/{agent_id}/sessions/{session_id}", json={k: v for k, v in {"input": input, "model": model, "temperature": temperature, "timeout": timeout}.items() if v is not None}, timeout=timeout)

    def delete_session(self, agent_id: str, session_id: str) -> bool:
        return self._ok("DELETE", f"/agents/{agent_id}/sessions/{session_id}")

class AsyncAgents(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/agents", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, agent_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/agents/{agent_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `model`, `instructions`, `tools`, `chat`."""
        return await self._json("POST", "/agents", json=data)

    async def update(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("PATCH", f"/agents/{agent_id}", json=data)

    async def delete(self, agent_id: str) -> bool:
        return await self._ok("DELETE", f"/agents/{agent_id}")

    async def restore(self, agent_id: str) -> Dict[str, Any]:
        return await self._json("POST", f"/agents/{agent_id}/restore")

    async def versions(self, agent_id: str, *, limit: Optional[int] = None, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/agents/{agent_id}/versions", params={"limit": limit, "branch": branch})

    async def version(self, agent_id: str, version_id: str, *, branch: Optional[str] = None) -> Dict[str, Any]:
        return await self._json("GET", f"/agents/{agent_id}/versions/{version_id}", params={"branch": branch})

    async def tool_registry(self) -> List[Dict[str, Any]]:
        """Every tool an agent may be given."""
        return await self._list("GET", "/agents/tools")

    async def tools(self, agent_id: str, *, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/agents/{agent_id}/tools", params={"branch": branch})

    async def invoke_tool(self, agent_id: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None, *, branch: Optional[str] = None) -> Any:
        return await self._json("POST", f"/agents/{agent_id}/tools/{tool_name}/invoke", json={"arguments": arguments or {}}, params={"branch": branch})

    async def sessions(self, agent_id: str) -> List[Dict[str, Any]]:
        return await self._list("GET", f"/agents/{agent_id}/sessions")

    async def session(self, agent_id: str, session_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/agents/{agent_id}/sessions/{session_id}")

    async def start_session(self, agent_id: str, input: Any, *, model: Optional[str] = None, temperature: Optional[float] = None, timeout: Optional[float] = None, branch: Optional[str] = None) -> Dict[str, Any]:
        """Open a conversation with the agent; answers the session and its first reply."""
        return await self._json("POST", f"/agents/{agent_id}/sessions", json={k: v for k, v in {"input": input, "model": model, "temperature": temperature, "timeout": timeout}.items() if v is not None}, params={"branch": branch}, timeout=timeout)

    async def continue_session(self, agent_id: str, session_id: str, input: Any, *, model: Optional[str] = None, temperature: Optional[float] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        return await self._json("POST", f"/agents/{agent_id}/sessions/{session_id}", json={k: v for k, v in {"input": input, "model": model, "temperature": temperature, "timeout": timeout}.items() if v is not None}, timeout=timeout)

    async def delete_session(self, agent_id: str, session_id: str) -> bool:
        return await self._ok("DELETE", f"/agents/{agent_id}/sessions/{session_id}")
