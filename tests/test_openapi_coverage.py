"""Every route of the catalog's OpenAPI (a snapshot in tests/data) is wrapped
by some SDK method, except the ones listed as deliberately left out. The
SDK's routes are read from its source: every `url=` or `_json("GET", f"...")`
string, with path parameters normalised."""

import json
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "gwenlake"
SPEC = Path(__file__).parent / "data" / "openapi.json"

#: Routes the SDK does not wrap on purpose (internal, or served by other means).
LEFT_OUT = {
    "/healthcheck", "/internal/{...}", "/klara", "/klara/{...}", "/rerank",
    "/mlmodels/{...}/artifacts/{...}",          # LFS upload: the training module's git push does it
    "/connections/test",                         # configuration test before creation: UI concern
    "/filesystem/projects/{...}/agents", "/filesystem/projects/{...}/applications",
    "/filesystem/projects/{...}/connections", "/filesystem/projects/{...}/repositories",
    "/filesystem/projects/{...}/schedules",      # the same listings exist as `<resource>.list(project_id=)`
}


def _normalise(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{...}", path)


def sdk_routes() -> set:
    routes = set()
    for file in SRC.glob("*.py"):
        text = file.read_text()
        for match in re.finditer(r'(?:url=|_json\(|_list\(|_ok\(|_bytes\(|_send\()\s*(?:"[A-Z]+",\s*)?f?"(/[^"]+)"', text):
            url = match.group(1)
            url = re.sub(r"\{[^}]+\}", "{...}", url)
            url = re.sub(r'" \+ \(.*', "", url)
            routes.add(url)
        # routes built with string concatenation or format in files.py / connections.py
        for match in re.finditer(r'f?"(/(?:datasets|connections|mediasets|filesystem|sql|chat|embeddings|models|rerank)[^"]*)"', text):
            routes.add(re.sub(r"\{[^}]+\}", "{...}", match.group(1)))
    return routes


def test_every_openapi_route_is_wrapped():
    spec = json.loads(SPEC.read_text())
    expected = {_normalise(p) for p in spec["paths"]}
    wrapped = sdk_routes()
    # a wrapped prefix covers the `.../files/{path}` upload variant and the like
    def covered(path: str) -> bool:
        if path in wrapped or path in LEFT_OUT:
            return True
        if any(path.startswith(prefix.replace("{...}", "")) for prefix in LEFT_OUT if prefix.endswith("{...}")):
            return True
        return False
    missing = sorted(p for p in expected if not covered(p))
    assert not missing, "routes of the API without an SDK method:\n  " + "\n  ".join(missing)
