"""Every new resource against the fake API: the route it calls, the query
and body it sends, what it returns."""

import io

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from gwenlake._resource import JobFailed
from gwenlake.exceptions import GwenlakeException
from gwenlake.schedules import build_action, time_trigger

LISTING = {"object": "list", "data": [{"id": "res.x.1", "alias": "a"}, {"id": "res.x.2", "alias": "b"}]}


def test_list_answers_are_unwrapped_and_none_params_dropped(api, client):
    api.routes[("GET", "/schedules")] = LISTING
    rows = client.schedules.list(project_id="res.project.p")
    assert [r["alias"] for r in rows] == ["a", "b"]
    assert api.last()["query"] == {"project_id": "res.project.p"}          # organization_id was None: not sent
    assert api.last()["headers"]["authorization"] == "Bearer test-key"


def test_schedules_crud_and_trigger(api, client):
    api.routes[("POST", "/schedules")] = {"id": "res.schedule.1"}
    api.routes[("GET", "/schedules/{id}")] = {"id": "res.schedule.1", "name": "Nightly"}
    api.routes[("PATCH", "/schedules/{id}")] = {"id": "res.schedule.1", "enabled": False}
    api.routes[("POST", "/schedules/{id}/trigger")] = {"fired": True}
    api.routes[("DELETE", "/schedules/{id}")] = 204
    body = {"name": "Nightly", "project_id": "res.project.p", "trigger": time_trigger("0 6 * * *", "Europe/Paris"),
            "action": build_action("res.dataset.d"), "enabled": True}
    assert client.schedules.create(body)["id"] == "res.schedule.1"
    assert api.last()["json"]["trigger"] == {"type": "time", "cron": "0 6 * * *", "time_zone": "Europe/Paris"}
    assert api.last()["json"]["action"] == {"type": "build", "target_ids": ["res.dataset.d"]}
    # the catalog wants `name` in a PATCH: update fetches it when absent
    client.schedules.enable("res.schedule.1", False)
    assert api.paths()[-2:] == ["GET /schedules/res.schedule.1", "PATCH /schedules/res.schedule.1"]
    assert api.last()["json"] == {"name": "Nightly", "enabled": False}
    assert client.schedules.trigger("res.schedule.1") == {"fired": True}
    assert client.schedules.delete("res.schedule.1") is True


def test_transform_parameters_merge_into_the_config(api, client):
    api.routes[("GET", "/transforms/{id}")] = {"id": "res.transform.t", "config": {
        "entrypoint": "src/x.py", "function": "f", "parameters": {"listen_seconds": 600}}}
    api.routes[("PATCH", "/transforms/{id}")] = lambda req: __import__("httpx").Response(200, json=__import__("json").loads(req.content), request=req)
    updated = client.transforms.set_parameters("res.transform.t", {"api_key": "k"})
    assert updated["config"] == {"entrypoint": "src/x.py", "function": "f", "parameters": {"listen_seconds": 600, "api_key": "k"}}
    client.transforms.set_parameters("res.transform.t", {"api_key": "k"}, merge=False)
    assert api.last()["json"]["config"]["parameters"] == {"api_key": "k"}
    assert api.last()["json"]["config"]["entrypoint"] == "src/x.py"       # the rest of the config survives


def test_transforms_list_filters_by_output_and_lists_functions(api, client):
    api.routes[("GET", "/transforms")] = LISTING
    api.routes[("GET", "/transforms/functions")] = {"object": "list", "data": [{"name": "dedupe"}]}
    client.transforms.list(output="res.dataset.d")
    assert api.last()["query"] == {"output": "res.dataset.d"}
    assert client.transforms.functions() == [{"name": "dedupe"}]


def test_builds_run_wait_and_logs(api, client, monkeypatch):
    monkeypatch.setattr("gwenlake._resource.time.sleep", lambda s: None)
    states = iter(["PENDING", "RUNNING", "SUCCESS"])
    api.routes[("POST", "/orchestration/builds")] = {"group_id": "g", "target_id": "res.dataset.d",
                                                      "builds": [{"id": "build.up", "status": "PENDING"}, {"id": "build.t", "status": "PENDING"}]}
    api.routes[("GET", "/orchestration/builds/{id}")] = lambda req: __import__("httpx").Response(
        200, json={"id": str(req.url).rsplit("/", 1)[-1], "status": next(states, "SUCCESS")}, request=req)
    api.routes[("GET", "/orchestration/builds/{id}/logs")] = {"logs": "line1\nline2"}
    batch = client.builds.run_and_wait("res.dataset.d", target_only=True, branch="trial", interval=0)
    assert api.calls[0]["json"] == {"target_id": "res.dataset.d", "target_only": True, "branch": "trial"}
    assert [b["status"] for b in batch["builds"]] == ["SUCCESS", "SUCCESS"]
    assert "GET /orchestration/builds/build.t" in api.paths()
    assert client.builds.logs("build.t", tail=50)["logs"].startswith("line1")
    assert api.last()["query"] == {"tail": "50"}


def test_a_failed_build_raises_unless_asked_not_to(api, client, monkeypatch):
    monkeypatch.setattr("gwenlake._resource.time.sleep", lambda s: None)
    api.routes[("GET", "/orchestration/builds/{id}")] = {"id": "build.f", "status": "FAILED", "error_message": "worker lost"}
    with pytest.raises(JobFailed, match="worker lost") as exc:
        client.builds.wait("build.f", interval=0)
    assert exc.value.job["status"] == "FAILED"
    assert client.builds.wait("build.f", interval=0, raise_on_failure=False)["status"] == "FAILED"


def test_wait_gives_up_at_the_timeout(api, client, monkeypatch):
    monkeypatch.setattr("gwenlake._resource.time.sleep", lambda s: None)
    clock = iter([0, 0, 100, 200])
    monkeypatch.setattr("gwenlake._resource.time.monotonic", lambda: next(clock))
    api.routes[("GET", "/orchestration/tasks/{id}")] = {"task_id": "t", "status": "PENDING"}
    with pytest.raises(GwenlakeException, match="still PENDING"):
        client.builds.wait_task("t", timeout=50, interval=0)


def test_repository_scan_waits_for_its_task(api, client, monkeypatch):
    monkeypatch.setattr("gwenlake._resource.time.sleep", lambda s: None)
    api.routes[("POST", "/orchestration/repositories/{id}/scan-lineage")] = {"repository_id": "res.repository.r", "task_id": "task-1"}
    api.routes[("GET", "/orchestration/tasks/{id}")] = {"task_id": "task-1", "status": "SUCCESS", "result": {"transforms_found": 7}}
    assert client.repositories.scan_lineage("res.repository.r") == {"repository_id": "res.repository.r", "task_id": "task-1"}
    assert api.last()["query"] == {}
    result = client.repositories.scan_lineage("res.repository.r", ref="main", wait=True)
    assert result["result"]["transforms_found"] == 7
    assert api.calls[-2]["query"] == {"ref": "main"}


def test_git_routes(api, client):
    api.routes[("GET", "/git/{id}/tree")] = [{"path": "sql"}]
    api.routes[("POST", "/git/{id}/commit")] = {"sha": "abc"}
    assert client.repositories.tree("res.repository.r", ref="main", path="sql") == [{"path": "sql"}]
    assert api.last()["query"] == {"ref": "main", "path": "sql"}
    client.repositories.commit("res.repository.r", ref="main", message="m", changes=[{"path": "a.sql", "content": "x"}])
    assert api.last()["json"] == {"ref": "main", "message": "m", "changes": [{"path": "a.sql", "content": "x"}]}


def test_datasets_update_delete_rows_and_resolve(api, client):
    api.routes[("PATCH", "/datasets/{id}")] = {"id": "res.dataset.d", "name": "New"}
    api.routes[("GET", "/filesystem/projects")] = {"object": "list", "data": [{"id": "res.project.p", "alias": "fleetsight"}]}
    api.routes[("GET", "/datasets")] = {"object": "list", "data": [{"id": "res.dataset.d", "alias": "aisdk_positions"}]}
    assert client.datasets.update("res.dataset.d", {"name": "New"})["name"] == "New"
    assert client.resolve("fleetsight.aisdk_positions") == "res.dataset.d"
    assert client.resolve("res.dataset.zzz") == "res.dataset.zzz"
    with pytest.raises(GwenlakeException, match="No dataset 'nope'"):
        client.resolve("fleetsight.nope")
    # DELETE by filter is a write without a file; "no table yet" is not an error
    api.routes[("POST", "/datasets/{id}/files")] = (400, {"detail": "This Iceberg dataset has no table yet — nothing to delete."})
    assert client.datasets.delete_rows("res.dataset.d", "source_file = 'x.csv'") is False
    assert api.last()["query"] == {"mode": "DELETE", "delete_filter": "source_file = 'x.csv'"}
    api.routes[("POST", "/datasets/{id}/files")] = {"ok": True}
    assert client.datasets.delete_rows("res.dataset.d", "source_file = 'x.csv'", branch="trial") is True
    assert api.last()["query"]["branch"] == "trial"


def test_dataset_branches_summary_and_maintenance(api, client):
    api.routes[("GET", "/datasets/{id}/summary")] = {"rows": 10}
    api.routes[("GET", "/datasets/{id}/branches")] = {"object": "list", "data": [{"name": "main"}]}
    api.routes[("POST", "/datasets/{id}/branches/{b}/promote")] = {"promoted": True}
    api.routes[("POST", "/datasets/{id}/maintenance")] = {"ok": True}
    assert client.datasets.summary("res.dataset.d") == {"rows": 10}
    assert client.datasets.branches("res.dataset.d") == [{"name": "main"}]
    client.datasets.promote_branch("res.dataset.d", "trial", delete=True)
    assert api.last()["query"] == {"delete": "true"}
    client.datasets.maintenance("res.dataset.d", older_than_days=7)
    assert api.last()["query"] == {"older_than_days": "7"}


def _ipc(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with pa.ipc.new_file(sink, table.schema) as w:
        w.write_table(table)
    return sink.getvalue().to_pybytes()


def _paged_statements(api, total_rows: int, page_rows: int):
    """A dataset of `total_rows` rows served through LIMIT/OFFSET pages."""
    import httpx, json, re

    def answer(req):
        statement = json.loads(req.content)["statement"]
        m = re.search(r"LIMIT (\d+) OFFSET (\d+)", statement)
        if m:
            limit, offset = int(m.group(1)), int(m.group(2))
            ids = list(range(offset, min(offset + limit, total_rows)))
        else:
            ids = list(range(min(total_rows, 1000)))
        table = pa.table({"id": pa.array(ids, pa.int64()), "name": [f"v{i}" for i in ids]})
        return httpx.Response(200, content=_ipc(table), request=req)
    api.routes[("POST", "/sql/statements")] = answer


def test_iter_arrow_pages_until_a_short_page(api, client):
    _paged_statements(api, total_rows=250, page_rows=100)
    pages = list(client.statements.iter_arrow("SELECT * FROM 'p.d' ORDER BY id", page_rows=100))
    assert [p.num_rows for p in pages] == [100, 100, 50]
    sent = [c["json"]["statement"] for c in api.calls]
    assert sent[0] == "SELECT * FROM (SELECT * FROM 'p.d' ORDER BY id) AS __page LIMIT 100 OFFSET 0"
    assert all(c["json"]["format"] == "pyarrow" for c in api.calls)
    assert client.statements.read_all("SELECT * FROM 'p.d'", page_rows=100).num_rows == 250
    # a statement with its own LIMIT is one page, sent as is
    list(client.statements.iter_arrow("SELECT * FROM 'p.d' LIMIT 5"))
    assert api.last()["json"]["statement"] == "SELECT * FROM 'p.d' LIMIT 5"


@pytest.mark.parametrize("ext", ["parquet", "csv", "json", "jsonl"])
def test_to_file_writes_every_format(api, client, tmp_path, ext):
    import csv, json

    _paged_statements(api, total_rows=120, page_rows=50)
    out = tmp_path / f"result.{ext}"
    assert client.statements.to_file("SELECT * FROM 'p.d'", str(out), page_rows=50) == 120
    if ext == "parquet":
        table = pq.read_table(out)
        assert table.num_rows == 120 and table.column("id").to_pylist()[:3] == [0, 1, 2]
    elif ext == "csv":
        rows = list(csv.DictReader(out.open()))
        assert len(rows) == 120 and rows[0] == {"id": "0", "name": "v0"}          # one header only
    elif ext == "json":
        rows = json.loads(out.read_text())
        assert len(rows) == 120 and rows[-1] == {"id": 119, "name": "v119"}
    else:
        lines = out.read_text().splitlines()
        assert len(lines) == 120 and json.loads(lines[0]) == {"id": 0, "name": "v0"}


def test_to_file_refuses_an_unknown_extension(client, tmp_path):
    with pytest.raises(GwenlakeException, match="cannot tell the format"):
        client.statements.to_file("SELECT 1", str(tmp_path / "x.xlsx"))


def test_generated_resources_hit_their_routes(api, client):
    api.routes[("GET", "/users/me")] = {"email": "me@x"}
    api.routes[("GET", "/mlmodels")] = LISTING
    api.routes[("POST", "/api-keys")] = {"id": "k", "secret": "s"}
    api.routes[("GET", "/filesystem/search")] = LISTING
    api.routes[("POST", "/agents/{id}/sessions")] = {"session_id": "s1"}
    api.routes[("GET", "/organizations/{id}/members")] = LISTING
    api.routes[("GET", "/lineage/projects/{id}")] = {"nodes": []}
    api.routes[("GET", "/orchestration/lineage/{id}")] = {"nodes": [], "edges": []}
    api.routes[("POST", "/orchestration/branches")] = {"branch": "trial"}
    api.routes[("GET", "/sql/queries/{id}")] = {"sql": "SELECT 1"}
    assert client.users.me()["email"] == "me@x"
    assert len(client.ml_models.list(project_id="res.project.p")) == 2
    client.api_keys.create(name="ci", project_id="res.project.p")
    assert api.last()["json"] == {"name": "ci", "project_id": "res.project.p"}
    client.filesystem.search("ais", type="dataset")
    assert api.last()["query"] == {"q": "ais", "type": "dataset"}
    client.agents.start_session("res.agent.a", "hello", temperature=0.2)
    assert api.last()["json"] == {"input": "hello", "temperature": 0.2}
    assert len(client.organizations.members("res.organization.o")) == 2
    assert client.lineage.project("res.project.p") == {"nodes": []}
    client.lineage.graph("res.dataset.d", direction="upstream")
    assert api.last()["query"] == {"direction": "upstream"}
    client.lineage.create_branch("res.dataset.d", "trial", build=True)
    assert api.last()["json"] == {"root_id": "res.dataset.d", "name": "trial", "from_branch": "main", "build": True}
    assert client.queries.get("res.sql-query.q", branch="trial")["sql"] == "SELECT 1"
    assert api.last()["query"] == {"branch": "trial"}


def test_base_url_comes_from_the_profile_when_nothing_else_says(monkeypatch):
    from gwenlake.client import _resolve_base_url
    from gwenlake.credentials import Credentials

    monkeypatch.delenv("GWENLAKE_BASE_URL", raising=False)
    tenant = Credentials(token="t", base_url="https://atlas.client.example/v1")
    assert _resolve_base_url(None, tenant) == "https://atlas.client.example/v1"
    assert _resolve_base_url("https://explicit/v1", tenant) == "https://explicit/v1"
    monkeypatch.setenv("GWENLAKE_BASE_URL", "https://env/v1")
    assert _resolve_base_url(None, tenant) == "https://env/v1"
    assert _resolve_base_url(None, Credentials(token="t")) == "https://env/v1"
    monkeypatch.delenv("GWENLAKE_BASE_URL")
    assert _resolve_base_url(None, Credentials(token="t")) == "https://api.gwenlake.com/v1"
