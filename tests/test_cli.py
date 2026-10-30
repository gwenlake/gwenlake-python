"""The command line against the fake API, through click's runner."""

import json

import pyarrow as pa
import pytest
from click.testing import CliRunner

from gwenlake import cli
from conftest import FakeApi, fake_client

PROJECTS = {"object": "list", "data": [{"id": "res.project.p", "alias": "fleetsight", "name": "FleetSight", "updated_at": "2026-10-29T10:00:00Z"}]}
DATASETS = {"object": "list", "data": [{"id": "res.dataset.d", "alias": "aisdk_positions", "name": "AISDK positions", "type": "iceberg", "updated_at": "2026-10-29"}]}


@pytest.fixture
def api(monkeypatch):
    api = FakeApi({("GET", "/filesystem/projects"): PROJECTS, ("GET", "/datasets"): DATASETS})
    monkeypatch.setattr(cli, "make_client", lambda **kw: fake_client(api))
    return api


def run(*args, input=None):
    result = CliRunner().invoke(cli.main, list(args), input=input, catch_exceptions=False)
    return result


def test_listings_print_a_table_or_json(api):
    out = run("datasets", "list", "--project", "fleetsight").output
    assert "aisdk_positions" in out and out.splitlines()[0].startswith("id")
    assert api.calls[-1]["query"] == {"project_id": "res.project.p"}       # the slug was resolved
    out = run("--json", "projects", "list").output
    assert json.loads(out)[0]["alias"] == "fleetsight"


def test_a_dataset_is_named_project_dot_dataset(api):
    api.routes[("GET", "/datasets/{id}")] = {"id": "res.dataset.d", "alias": "aisdk_positions"}
    result = run("datasets", "get", "fleetsight.aisdk_positions")
    assert result.exit_code == 0 and api.paths()[-1] == "GET /datasets/res.dataset.d"
    result = run("datasets", "get", "fleetsight.nope")
    assert result.exit_code == 1 and "No dataset 'nope'" in result.output


def _ipc(table):
    sink = pa.BufferOutputStream()
    with pa.ipc.new_file(sink, table.schema) as w:
        w.write_table(table)
    return sink.getvalue().to_pybytes()


def test_sql_prints_rows_or_writes_a_file(api, tmp_path):
    table = pa.table({"zone": ["brest", "gulf_of_lion"], "n": [3, 5]})
    api.routes[("POST", "/sql/statements")] = _ipc(table)
    out = run("sql", "SELECT zone, count(*) n FROM 'fleetsight.aisdk_positions' GROUP BY 1", "--limit", "10").output
    assert "brest" in out and "gulf_of_lion" in out
    assert api.last()["json"]["limit"] == 10 and api.last()["json"]["format"] == "pyarrow"
    target = tmp_path / "zones.parquet"
    result = run("sql", "SELECT 1 LIMIT 1", "--out", str(target))
    assert result.exit_code == 0 and "2 rows written" in result.output and target.exists()


def test_sql_writes_to_stdout(api):
    import io
    import pyarrow.parquet as pq

    api.routes[("POST", "/sql/statements")] = _ipc(pa.table({"zone": ["brest", "gulf_of_lion"]}))
    result = CliRunner().invoke(cli.main, ["sql", "SELECT 1", "-o", "-", "--format", "parquet"], catch_exceptions=False)
    assert result.exit_code == 0 and "2 rows written to stdout" in result.stderr
    assert pq.read_table(io.BytesIO(result.stdout_bytes)).column("zone").to_pylist() == ["brest", "gulf_of_lion"]
    result = CliRunner().invoke(cli.main, ["sql", "SELECT 1", "-o", "-"])
    assert result.exit_code != 0 and "--format" in result.output


def test_export_writes_a_whole_dataset(api, tmp_path):
    table = pa.table({"id": [1, 2]})
    api.routes[("POST", "/sql/statements")] = _ipc(table)
    target = tmp_path / "positions.csv"
    result = run("datasets", "export", "fleetsight.aisdk_positions", "--out", str(target), "--where", "zone = 'brest'")
    assert result.exit_code == 0
    assert api.last()["json"]["statement"].startswith("SELECT * FROM (SELECT * FROM 'fleetsight.aisdk_positions' WHERE zone = 'brest') AS __page LIMIT 50000 OFFSET 0")
    assert target.read_text().splitlines()[0] == '"id"'


def test_builds_run_resolves_the_target_and_waits(api, monkeypatch):
    monkeypatch.setattr("gwenlake._resource.time.sleep", lambda s: None)
    api.routes[("POST", "/orchestration/builds")] = {"group_id": "g", "target_id": "res.dataset.d", "builds": [{"id": "build.1", "status": "PENDING"}]}
    api.routes[("GET", "/orchestration/builds/{id}")] = {"id": "build.1", "status": "SUCCESS", "target_id": "res.dataset.d"}
    result = run("builds", "run", "fleetsight.aisdk_positions", "--target-only", "--wait")
    assert result.exit_code == 0 and "SUCCESS" in result.output
    assert api.calls[-3]["json"] == {"target_id": "res.dataset.d", "target_only": True}
    api.routes[("GET", "/orchestration/builds/{id}")] = {"id": "build.1", "status": "FAILED", "error_message": "boom"}
    assert run("builds", "run", "fleetsight.aisdk_positions", "--wait").exit_code == 1


def test_schedules_create_builds_the_trigger_and_action(api):
    api.routes[("POST", "/schedules")] = {"id": "res.schedule.s"}
    result = run("schedules", "create", "--project", "fleetsight", "--name", "Nightly", "--cron", "0 6 * * *",
                 "--time-zone", "Europe/Paris", "--target", "fleetsight.aisdk_positions")
    assert result.exit_code == 0
    assert api.last()["json"] == {"name": "Nightly", "project_id": "res.project.p", "enabled": True,
                                  "trigger": {"type": "time", "cron": "0 6 * * *", "time_zone": "Europe/Paris"},
                                  "action": {"type": "build", "target_ids": ["res.dataset.d"]}}


def test_transform_parameters_accept_json_values(api):
    api.routes[("GET", "/transforms/{id}")] = {"id": "res.transform.t", "config": {"function": "f"}}
    api.routes[("PATCH", "/transforms/{id}")] = {"id": "res.transform.t"}
    run("transforms", "set-parameters", "res.transform.t", "listen_seconds=600", 'zones=[{"slug":"x"}]', "api_key=abc")
    assert api.last()["json"]["config"]["parameters"] == {"listen_seconds": 600, "zones": [{"slug": "x"}], "api_key": "abc"}


def test_config_profiles_are_written_to_the_credentials_file(monkeypatch, tmp_path):
    path = tmp_path / "credentials"
    monkeypatch.setattr(cli.Credentials, "_default_config_path", staticmethod(lambda: str(path)))
    probed = []
    monkeypatch.setattr(cli, "probe_endpoint", lambda url, token: probed.append((url, token)) or "https://atlas.client.example/api/v1")
    result = run("config", "set-profile", "client", "--token", "sk-1234567890abcdef", "--base-url", "atlas.client.example")
    assert result.exit_code == 0 and path.exists() and probed == [("atlas.client.example", "sk-1234567890abcdef")]
    assert "[client]" in path.read_text() and "base_url = https://atlas.client.example/api/v1" in path.read_text()
    result = run("config", "set-profile", "client", "--base-url", "atlas.client.example/api", "--no-probe")
    assert result.exit_code == 0 and "base_url = https://atlas.client.example/api/v1" in path.read_text()
    monkeypatch.setattr(cli, "probe_endpoint", lambda url, token: None)
    result = run("config", "set-profile", "client", "--base-url", "nowhere.example")
    assert result.exit_code == 1 and "no API found" in result.output
    out = run("config", "list").output
    assert "client" in out and "sk-123...cdef" in out and "sk-1234567890abcdef" not in out
    assert run("config", "remove-profile", "client").exit_code == 0 and "[client]" not in path.read_text()
    assert run("config", "path").output.strip() == str(path)

    from gwenlake.credentials import Credentials
    (tmp_path / "credentials").write_text("[tenant]\ntoken = t\nbase_url = https://tenant/v1\n\n[acme]\ntoken = t\nhost = atlas.acme.example\n")
    monkeypatch.setattr(Credentials, "_default_config_path", staticmethod(lambda: str(path)))
    assert Credentials.from_profile("tenant").base_url == "https://tenant/v1"
    assert Credentials.from_profile("acme").base_url == "atlas.acme.example"            # completed by the client:
    from gwenlake.client import _resolve_base_url
    monkeypatch.delenv("GWENLAKE_BASE_URL", raising=False)
    assert _resolve_base_url(None, Credentials.from_profile("acme")) == "https://atlas.acme.example/v1"


def test_the_endpoint_can_be_given_on_the_command_line(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "make_client", lambda **kw: seen.update(kw) or fake_client(FakeApi({("GET", "/users/me"): {"email": "x"}})))
    assert run("--base-url", "https://atlas.client.example/v1", "--profile", "client", "me").exit_code == 0
    assert seen == {"profile": "client", "api_key": None, "base_url": "https://atlas.client.example/v1"}


def test_the_global_options_also_follow_the_command(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "make_client", lambda **kw: seen.update(kw) or fake_client(FakeApi({("GET", "/users/me"): {"email": "x"}})))
    result = run("me", "--profile", "client", "--base-url", "https://atlas.client.example/v1", "--json")
    assert result.exit_code == 0 and '"email": "x"' in result.output
    assert seen == {"profile": "client", "api_key": None, "base_url": "https://atlas.client.example/v1"}
    assert run("config", "list", "-p", "client").exit_code == 0


def test_config_endpoints_lists_the_known_ones(monkeypatch):
    monkeypatch.delenv("GWENLAKE_BASE_URL", raising=False)
    out = run("config", "endpoints").output
    assert "api    https://api.gwenlake.com/v1" in out and "atlas  https://atlas.gwenlake.com/api/v1" in out
    assert "current: https://api.gwenlake.com/v1" in out
    out = run("--base-url", "atlas", "config", "endpoints").output
    assert "current: https://atlas.gwenlake.com/api/v1" in out
