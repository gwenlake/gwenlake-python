"""`/schedules` — the catalog's timers: a cron trigger (evaluated in its own
IANA time zone) and an action, today a build of one or more datasets
(``{"type": "build", "target_ids": [...]}``), dependencies included.

A schedule is a project resource like any other: `create` takes the resource
fields (`name`, `project_id`, `description`...) with `trigger`, `action` and
`enabled`; `update` sends a partial body (the catalog requires `name` in it,
so `update` fills it in from the current state when it is not given).
"""

from typing import Any, Dict, List, Optional

from gwenlake._resource import AsyncResource, Resource


def time_trigger(cron: str, time_zone: str = "UTC") -> Dict[str, Any]:
    """A cron trigger, five or six fields, evaluated in `time_zone`."""
    return {"type": "time", "cron": cron, "time_zone": time_zone}


def build_action(*target_ids: str) -> Dict[str, Any]:
    """The action that builds the given datasets (their stale upstream chain included)."""
    return {"type": "build", "target_ids": list(target_ids)}


class Schedules(Resource):

    def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._list("GET", "/schedules", params={"project_id": project_id, "organization_id": organization_id})

    def get(self, schedule_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/schedules/{schedule_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """`data`: `name`, `project_id`, `trigger` (see `time_trigger`), `action`
        (see `build_action`), `enabled`, and the usual resource fields."""
        return self._json("POST", "/schedules", json=data)

    def update(self, schedule_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if "name" not in data:
            data = {"name": self.get(schedule_id)["name"], **data}
        return self._json("PATCH", f"/schedules/{schedule_id}", json=data)

    def delete(self, schedule_id: str) -> bool:
        return self._ok("DELETE", f"/schedules/{schedule_id}")

    def trigger(self, schedule_id: str) -> Any:
        """Fire the schedule now, as if its cron had just matched."""
        return self._json("POST", f"/schedules/{schedule_id}/trigger")

    def enable(self, schedule_id: str, enabled: bool = True) -> Dict[str, Any]:
        return self.update(schedule_id, {"enabled": enabled})


class AsyncSchedules(AsyncResource):

    async def list(self, *, project_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list("GET", "/schedules", params={"project_id": project_id, "organization_id": organization_id})

    async def get(self, schedule_id: str) -> Dict[str, Any]:
        return await self._json("GET", f"/schedules/{schedule_id}")

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json("POST", "/schedules", json=data)

    async def update(self, schedule_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if "name" not in data:
            data = {"name": (await self.get(schedule_id))["name"], **data}
        return await self._json("PATCH", f"/schedules/{schedule_id}", json=data)

    async def delete(self, schedule_id: str) -> bool:
        return await self._ok("DELETE", f"/schedules/{schedule_id}")

    async def trigger(self, schedule_id: str) -> Any:
        return await self._json("POST", f"/schedules/{schedule_id}/trigger")

    async def enable(self, schedule_id: str, enabled: bool = True) -> Dict[str, Any]:
        return await self.update(schedule_id, {"enabled": enabled})
