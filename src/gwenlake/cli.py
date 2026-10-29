"""The `gwenlake` command (alias `gwl`): the Gwenlake APIs and Gwenlake Atlas
from a terminal, in the noun-verb form of the SDK resources.

    gwenlake [--profile NAME] [--api-key KEY] [--base-url URL] [--json] <resource> <command> [...]

Credentials come, in order, from `--api-key`, `--profile` (a section of
`~/.gwenlake/credentials`), `GWENLAKE_API_KEY` (a `.env` of the current
directory is read first), then the `default` profile. The API endpoint is
`--base-url`, else `GWENLAKE_BASE_URL`, else the profile's `base_url`, else
`https://api.gwenlake.com/v1`: that is how a tenant deployed on its own host
is reached (`gwenlake config set-profile client --token ... --base-url ...`).

Datasets are named `<project>.<dataset>` (or by id); projects by slug or id.
Listings print as a table, `--json` prints what the API answered.
"""

import configparser
import json
import os
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import click
import httpx

from gwenlake import Gwenlake
from gwenlake.credentials import Credentials
from gwenlake.exceptions import GwenlakeException


class _Group(click.Group):
    """A group whose commands report API errors as one line, not a traceback."""

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                detail = exc.response.json().get("detail", detail)
            except ValueError:
                pass
            raise click.ClickException(f"{exc.request.method} {exc.request.url.path}: {exc.response.status_code} {detail}")
        except GwenlakeException as exc:
            raise click.ClickException(str(exc))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, default=str, ensure_ascii=False)
    else:
        text = str(value)
    return text if len(text) <= 60 else text[:57] + "..."


def table(rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> str:
    """A plain text table of `columns`, sized to its content."""
    if not rows:
        return "(nothing)"
    cells = [[_cell(r.get(c)) for c in columns] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(columns)]
    line = lambda values: "  ".join(v.ljust(widths[i]) for i, v in enumerate(values)).rstrip()
    return "\n".join([line(list(columns)), line(["-" * w for w in widths])] + [line(r) for r in cells])


def emit(ctx: click.Context, data: Any, columns: Optional[Sequence[str]] = None) -> None:
    """JSON when asked (or for anything that is not a list of rows), else a table."""
    if ctx.obj.json or columns is None or not isinstance(data, list):
        click.echo(json.dumps(data, indent=2, default=str, ensure_ascii=False))
    else:
        click.echo(table(data, columns))


RESOURCE_COLUMNS = ("id", "alias", "name", "updated_at")


# ---------------------------------------------------------------------------
# Session: the client and the name resolution
# ---------------------------------------------------------------------------

class Session:
    def __init__(self, *, profile: Optional[str], api_key: Optional[str], base_url: Optional[str], json_output: bool):
        self.profile, self.api_key, self.base_url, self.json = profile, api_key, base_url, json_output
        self._client: Optional[Gwenlake] = None

    @property
    def client(self) -> Gwenlake:
        if self._client is None:
            self._client = make_client(profile=self.profile, api_key=self.api_key, base_url=self.base_url)
        return self._client

    def project_id(self, value: Optional[str]) -> Optional[str]:
        """A project slug (or id) -> id; `None` stays `None`."""
        if not value or value.startswith("res.project."):
            return value
        match = next((p for p in self.client.projects.list() if value in (p.get("alias"), p.get("slug"))), None)
        if match is None:
            raise click.ClickException(f"no project '{value}'")
        return match["id"]

    def dataset_id(self, ref: str) -> str:
        """`<project>.<dataset>` (or an id) -> dataset id."""
        try:
            return self.client.resolve(ref)
        except GwenlakeException as exc:
            raise click.ClickException(str(exc))


def make_client(*, profile: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None) -> Gwenlake:
    """Build the client the way the docstring says; a `.env` of the current
    directory counts as environment."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # pragma: no cover
        pass
    try:
        return Gwenlake(profile=profile, api_key=api_key, base_url=base_url)
    except GwenlakeException as exc:
        raise click.ClickException(f"{exc} (set GWENLAKE_API_KEY, pass --api-key, or create a profile: gwenlake config set-profile)")


pass_session = click.make_pass_decorator(Session)


def _fields(pairs: Sequence[str]) -> Dict[str, Any]:
    """`key=value` arguments as a dict; a value that parses as JSON is parsed."""
    out: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise click.ClickException(f"expected key=value, got '{pair}'")
        key, value = pair.split("=", 1)
        try:
            out[key] = json.loads(value)
        except ValueError:
            out[key] = value
    return out


def _resource_body(name: Optional[str], description: Optional[str], fields: Sequence[str]) -> Dict[str, Any]:
    body = _fields(fields)
    if name:
        body["name"] = name
    if description is not None:
        body["description"] = description
    return body


# ---------------------------------------------------------------------------
# The command tree
# ---------------------------------------------------------------------------

@click.group(cls=_Group, context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--profile", "-p", default=None, envvar="GWENLAKE_PROFILE", help="Section of ~/.gwenlake/credentials to use.")
@click.option("--api-key", default=None, help="API key (else GWENLAKE_API_KEY, .env, or the profile).")
@click.option("--base-url", default=None, help="API endpoint, for a tenant on its own host (else GWENLAKE_BASE_URL or the profile's base_url).")
@click.option("--json", "json_output", is_flag=True, help="Print the API's JSON instead of a table.")
@click.version_option(package_name="gwenlake", prog_name="gwenlake")
@click.pass_context
def main(ctx: click.Context, profile: Optional[str], api_key: Optional[str], base_url: Optional[str], json_output: bool) -> None:
    """Gwenlake and Gwenlake Atlas from the terminal."""
    ctx.obj = Session(profile=profile, api_key=api_key, base_url=base_url, json_output=json_output)


# -- me / config ---------------------------------------------------------------

@main.command()
@pass_session
@click.pass_context
def me(ctx: click.Context, s: Session) -> None:
    """Who the credentials belong to."""
    emit(ctx, s.client.users.me())


@main.group()
def config() -> None:
    """The credentials file (~/.gwenlake/credentials) and its profiles."""


@config.command("path")
def config_path() -> None:
    """Where the credentials file is."""
    click.echo(Credentials._default_config_path())


@config.command("list")
@pass_session
@click.pass_context
def config_list(ctx: click.Context, s: Session) -> None:
    """The profiles of the credentials file (secrets masked)."""
    parser = configparser.ConfigParser()
    parser.read(Credentials._default_config_path())
    rows = []
    for section in parser.sections():
        info = parser[section]
        token = info.get("token") or ""
        rows.append({"profile": section, "auth": "token" if token else ("oauth" if info.get("client_id") else "none"),
                     "token": (token[:6] + "..." + token[-4:]) if len(token) > 12 else ("***" if token else ""),
                     "base_url": info.get("base_url") or "", "hostname": info.get("hostname") or ""})
    emit(ctx, rows, ("profile", "auth", "token", "base_url", "hostname"))


@config.command("set-profile")
@click.argument("name")
@click.option("--token", default=None, help="API key of the profile.")
@click.option("--base-url", default=None, help="API endpoint of the profile, e.g. https://atlas.example.com/v1.")
@click.option("--client-id", default=None)
@click.option("--client-secret", default=None)
@click.option("--hostname", default=None, help="OAuth host for client credentials.")
@click.option("--scopes", default=None, help="Comma-separated OAuth scopes.")
def config_set_profile(name: str, token: Optional[str], base_url: Optional[str], client_id: Optional[str],
                       client_secret: Optional[str], hostname: Optional[str], scopes: Optional[str]) -> None:
    """Create or update a profile. Only the given options change."""
    path = Credentials._default_config_path()
    parser = configparser.ConfigParser()
    parser.read(path)
    if not parser.has_section(name):
        parser.add_section(name)
    for key, value in {"token": token, "base_url": base_url, "client_id": client_id, "client_secret": client_secret,
                       "hostname": hostname, "scopes": scopes}.items():
        if value is not None:
            parser[name][key] = value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        parser.write(handle)
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - Windows
        pass
    click.echo(f"profile '{name}' written to {path}")


@config.command("remove-profile")
@click.argument("name")
def config_remove_profile(name: str) -> None:
    """Delete a profile."""
    path = Credentials._default_config_path()
    parser = configparser.ConfigParser()
    parser.read(path)
    if not parser.remove_section(name):
        raise click.ClickException(f"no profile '{name}' in {path}")
    with open(path, "w") as handle:
        parser.write(handle)
    click.echo(f"profile '{name}' removed")


# -- projects -------------------------------------------------------------------

@main.group()
def projects() -> None:
    """Projects."""


@projects.command("list")
@click.option("--organization", default=None, help="Organization id.")
@pass_session
@click.pass_context
def projects_list(ctx, s: Session, organization):
    emit(ctx, s.client.projects.list(organization_id=organization), ("id", "alias", "name", "updated_at"))


@projects.command("get")
@click.argument("project")
@pass_session
@click.pass_context
def projects_get(ctx, s: Session, project):
    emit(ctx, s.client.projects.get(s.project_id(project)))


@projects.command("create")
@click.option("--name", required=True)
@click.option("--organization", default=None, help="Organization id.")
@click.option("--description", default=None)
@pass_session
@click.pass_context
def projects_create(ctx, s: Session, name, organization, description):
    body = {"name": name}
    if organization:
        body["organization_id"] = organization
    if description:
        body["description"] = description
    emit(ctx, s.client.projects.create(body))


@projects.command("delete")
@click.argument("project")
@click.confirmation_option(prompt="Delete this project and everything in it?")
@pass_session
def projects_delete(s: Session, project):
    s.client.projects.delete(s.project_id(project))
    click.echo("deleted")


# -- datasets -------------------------------------------------------------------

@main.group()
def datasets() -> None:
    """Datasets: `<project>.<dataset>` or an id."""


@datasets.command("list")
@click.option("--project", default=None, help="Project slug or id.")
@pass_session
@click.pass_context
def datasets_list(ctx, s: Session, project):
    emit(ctx, s.client.datasets.list(project_id=s.project_id(project)), ("id", "alias", "name", "type", "updated_at"))


@datasets.command("get")
@click.argument("dataset")
@pass_session
@click.pass_context
def datasets_get(ctx, s: Session, dataset):
    emit(ctx, s.client.datasets.get(s.dataset_id(dataset)))


@datasets.command("summary")
@click.argument("dataset")
@pass_session
@click.pass_context
def datasets_summary(ctx, s: Session, dataset):
    """Rows, size, schema, last snapshot."""
    emit(ctx, s.client.datasets.summary(s.dataset_id(dataset)))


@datasets.command("create")
@click.option("--project", required=True, help="Project slug or id.")
@click.option("--name", required=True)
@click.option("--slug", default=None)
@click.option("--type", "dataset_type", default="iceberg", show_default=True, type=click.Choice(["iceberg", "files", "vector"]))
@click.option("--description", default=None)
@click.argument("fields", nargs=-1)
@pass_session
@click.pass_context
def datasets_create(ctx, s: Session, project, name, slug, dataset_type, description, fields):
    """Create a dataset; extra `key=value` fields go in the body (`columns='[...]'`)."""
    body = _resource_body(name, description, fields) | {"project_id": s.project_id(project), "type": dataset_type}
    if slug:
        body["slug"] = slug
    emit(ctx, s.client.datasets.create(body))


@datasets.command("update")
@click.argument("dataset")
@click.option("--name", default=None)
@click.option("--description", default=None)
@click.argument("fields", nargs=-1)
@pass_session
@click.pass_context
def datasets_update(ctx, s: Session, dataset, name, description, fields):
    """Update a dataset's fields (`--name`, `--description`, `slug=...`, `columns='[...]'`)."""
    body = _resource_body(name, description, fields)
    if not body:
        raise click.ClickException("nothing to update")
    emit(ctx, s.client.datasets.update(s.dataset_id(dataset), body))


@datasets.command("delete")
@click.argument("dataset")
@click.confirmation_option(prompt="Delete this dataset and its data?")
@pass_session
def datasets_delete(s: Session, dataset):
    s.client.datasets.delete(s.dataset_id(dataset))
    click.echo("deleted")


@datasets.command("empty")
@click.argument("dataset")
@click.option("--branch", default=None)
@click.confirmation_option(prompt="Remove every row of this dataset?")
@pass_session
def datasets_empty(s: Session, dataset, branch):
    s.client.datasets.empty(s.dataset_id(dataset), branch=branch)
    click.echo("emptied")


@datasets.command("delete-rows")
@click.argument("dataset")
@click.argument("filter")
@click.option("--branch", default=None)
@pass_session
def datasets_delete_rows(s: Session, dataset, filter, branch):
    """Delete the rows matching a row filter, e.g. "source_file = 'x.csv'"."""
    done = s.client.datasets.delete_rows(s.dataset_id(dataset), filter, branch=branch)
    click.echo("rows deleted" if done else "no table yet, nothing to delete")


@datasets.command("branches")
@click.argument("dataset")
@pass_session
@click.pass_context
def datasets_branches(ctx, s: Session, dataset):
    emit(ctx, s.client.datasets.branches(s.dataset_id(dataset)), ("name", "snapshot_id", "updated_at"))


@datasets.command("export")
@click.argument("dataset")
@click.option("--out", "-o", required=True, type=click.Path(dir_okay=False), help="Output file: .parquet, .csv, .json or .jsonl.")
@click.option("--format", "fmt", default=None, type=click.Choice(["parquet", "csv", "json", "jsonl"]), help="Override the extension.")
@click.option("--where", default=None, help="A WHERE clause without the keyword.")
@click.option("--columns", default="*", show_default=True, help="Comma-separated columns.")
@click.option("--page-rows", default=50_000, show_default=True, type=int)
@pass_session
def datasets_export(s: Session, dataset, out, fmt, where, columns, page_rows):
    """Write the whole dataset (or a filtered part of it) to a file."""
    ref = dataset if "." in dataset and not dataset.startswith("res.") else _ref_of(s, dataset)
    statement = f"SELECT {columns} FROM '{ref}'" + (f" WHERE {where}" if where else "")
    rows = s.client.statements.to_file(statement, out, format=fmt, page_rows=page_rows)
    click.echo(f"{rows} rows written to {out}")


def _ref_of(s: Session, dataset_id: str) -> str:
    """`<project>.<dataset>` of a dataset id, for a SQL FROM."""
    dataset = s.client.datasets.get(dataset_id)
    project = s.client.projects.get(dataset["project_id"])
    return f"{project['alias']}.{dataset['alias']}"


# -- files ----------------------------------------------------------------------

@main.group()
def files() -> None:
    """The files of a dataset."""


@files.command("list")
@click.argument("dataset")
@click.option("--path", default=None)
@click.option("--branch", default=None)
@pass_session
@click.pass_context
def files_list(ctx, s: Session, dataset, path, branch):
    emit(ctx, s.client.files.list(s.dataset_id(dataset), path, branch=branch), ("path", "size", "updated_at"))


@files.command("upload")
@click.argument("dataset")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--path", default=None, help="Destination path in the dataset.")
@click.option("--mode", default=None, type=click.Choice(["APPEND", "SNAPSHOT", "UPSERT"], case_sensitive=False), help="Iceberg write mode.")
@click.option("--branch", default=None)
@pass_session
@click.pass_context
def files_upload(ctx, s: Session, dataset, file, path, mode, branch):
    kwargs = {k: v for k, v in {"path": path, "mode": mode.upper() if mode else None, "branch": branch}.items() if v}
    emit(ctx, s.client.files.upload(s.dataset_id(dataset), file, **kwargs))


@files.command("download")
@click.argument("dataset")
@click.argument("filepath")
@click.option("--out", "-o", default=None, type=click.Path(dir_okay=False), help="Local file (default: the file's name).")
@click.option("--branch", default=None)
@pass_session
def files_download(s: Session, dataset, filepath, out, branch):
    content = s.client.files.download(s.dataset_id(dataset), filepath, branch=branch)
    target = out or os.path.basename(filepath)
    with open(target, "wb") as handle:
        handle.write(content)
    click.echo(f"{len(content)} bytes written to {target}")


@files.command("delete")
@click.argument("dataset")
@click.argument("filepath")
@click.option("--branch", default=None)
@pass_session
def files_delete(s: Session, dataset, filepath, branch):
    s.client.files.delete(s.dataset_id(dataset), filepath, branch=branch)
    click.echo("deleted")


# -- sql ------------------------------------------------------------------------

@main.command()
@click.argument("statement", required=False)
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True, dir_okay=False), help="Read the statement from a file.")
@click.option("--out", "-o", default=None, type=click.Path(dir_okay=False), help="Write the whole result to .parquet, .csv, .json or .jsonl.")
@click.option("--format", "fmt", default=None, type=click.Choice(["parquet", "csv", "json", "jsonl"]), help="Override the extension of --out.")
@click.option("--limit", default=None, type=int, help="Row cap when printing (default: the server's 1000).")
@click.option("--page-rows", default=50_000, show_default=True, type=int, help="Rows per request when writing a file.")
@click.option("--mode", default=None, type=click.Choice(["duckdb", "spark"]), help="Engine.")
@pass_session
@click.pass_context
def sql(ctx, s: Session, statement, sql_file, out, fmt, limit, page_rows, mode):
    """Run a SQL statement over datasets: FROM '<project>.<dataset>'.

    Prints the rows (a table, or --json), or writes the whole result with --out."""
    if sql_file:
        with open(sql_file) as handle:
            statement = handle.read()
    if not statement:
        raise click.ClickException("give a statement or --file")
    if out:
        rows = s.client.statements.to_file(statement, out, format=fmt, page_rows=page_rows, mode=mode)
        click.echo(f"{rows} rows written to {out}")
        return
    table_ = s.client.statements.read_arrow(statement, limit=limit, mode=mode)
    rows = table_.to_pylist()
    emit(ctx, rows, table_.schema.names if rows else None)


# -- builds ---------------------------------------------------------------------

BUILD_COLUMNS = ("id", "status", "target_id", "triggered_by", "started_at", "finished_at", "error_message")


@main.group()
def builds() -> None:
    """Builds: materialize a dataset, follow a build."""


@builds.command("run")
@click.argument("dataset")
@click.option("--target-only", is_flag=True, help="Build the target alone, not its stale upstream chain.")
@click.option("--branch", default=None, help="Iceberg data branch to build into.")
@click.option("--wait", is_flag=True, help="Follow the build to its end.")
@click.option("--timeout", default=3600, show_default=True, type=float)
@pass_session
@click.pass_context
def builds_run(ctx, s: Session, dataset, target_only, branch, wait, timeout):
    target = s.dataset_id(dataset)
    batch = s.client.builds.run(target, target_only=target_only, branch=branch)
    if wait:
        s.client.builds.wait(batch["builds"][-1]["id"], timeout=timeout, raise_on_failure=False)
        batch["builds"] = [s.client.builds.get(b["id"]) for b in batch["builds"]]
    emit(ctx, batch["builds"], BUILD_COLUMNS)
    failed = [b for b in batch["builds"] if str(b.get("status")) in ("FAILED", "CANCELLED")]
    if wait and failed:
        sys.exit(1)


@builds.command("list")
@click.option("--target", default=None, help="Dataset ref or id.")
@click.option("--status", default=None)
@click.option("--limit", default=20, show_default=True, type=int, help="Most recent builds to show.")
@pass_session
@click.pass_context
def builds_list(ctx, s: Session, target, status, limit):
    # The listing is cut client-side: the API's own `limit` answers nothing for small values (catalog bug, Oct 2026).
    rows = s.client.builds.list(target_id=s.dataset_id(target) if target else None, status=status)
    rows = sorted(rows, key=lambda b: b.get("started_at") or "", reverse=True)[:limit]
    emit(ctx, rows, BUILD_COLUMNS)


@builds.command("get")
@click.argument("build_id")
@pass_session
@click.pass_context
def builds_get(ctx, s: Session, build_id):
    emit(ctx, s.client.builds.get(build_id))


@builds.command("logs")
@click.argument("build_id")
@click.option("--tail", default=None, type=int)
@pass_session
@click.pass_context
def builds_logs(ctx, s: Session, build_id, tail):
    answer = s.client.builds.logs(build_id, tail=tail)
    if ctx.obj.json:
        emit(ctx, answer)
    else:
        click.echo(answer.get("logs") if isinstance(answer, dict) else answer)


@builds.command("wait")
@click.argument("build_id")
@click.option("--timeout", default=3600, show_default=True, type=float)
@pass_session
@click.pass_context
def builds_wait(ctx, s: Session, build_id, timeout):
    build = s.client.builds.wait(build_id, timeout=timeout, raise_on_failure=False)
    emit(ctx, build)
    if str(build.get("status")) in ("FAILED", "CANCELLED"):
        sys.exit(1)


@builds.command("cancel")
@click.argument("build_id")
@pass_session
@click.pass_context
def builds_cancel(ctx, s: Session, build_id):
    emit(ctx, s.client.builds.cancel(build_id))


# -- schedules ------------------------------------------------------------------

SCHEDULE_COLUMNS = ("id", "name", "trigger", "action", "enabled")


@main.group()
def schedules() -> None:
    """Schedules: a cron, a build."""


@schedules.command("list")
@click.option("--project", default=None)
@pass_session
@click.pass_context
def schedules_list(ctx, s: Session, project):
    emit(ctx, s.client.schedules.list(project_id=s.project_id(project)), SCHEDULE_COLUMNS)


@schedules.command("get")
@click.argument("schedule_id")
@pass_session
@click.pass_context
def schedules_get(ctx, s: Session, schedule_id):
    emit(ctx, s.client.schedules.get(schedule_id))


@schedules.command("create")
@click.option("--project", required=True)
@click.option("--name", required=True)
@click.option("--cron", required=True, help='Five fields, e.g. "0 6 * * *".')
@click.option("--time-zone", default="UTC", show_default=True)
@click.option("--target", "targets", multiple=True, required=True, help="Dataset to build (ref or id); repeatable.")
@click.option("--disabled", is_flag=True)
@pass_session
@click.pass_context
def schedules_create(ctx, s: Session, project, name, cron, time_zone, targets, disabled):
    from gwenlake.schedules import build_action, time_trigger

    body = {"name": name, "project_id": s.project_id(project), "trigger": time_trigger(cron, time_zone),
            "action": build_action(*(s.dataset_id(t) for t in targets)), "enabled": not disabled}
    emit(ctx, s.client.schedules.create(body))


@schedules.command("update")
@click.argument("schedule_id")
@click.option("--name", default=None)
@click.option("--cron", default=None)
@click.option("--time-zone", default=None)
@click.option("--target", "targets", multiple=True, help="Replace the datasets to build.")
@click.option("--enable/--disable", default=None)
@pass_session
@click.pass_context
def schedules_update(ctx, s: Session, schedule_id, name, cron, time_zone, targets, enable):
    from gwenlake.schedules import build_action

    current = s.client.schedules.get(schedule_id)
    body: Dict[str, Any] = {"name": name or current["name"]}
    if cron or time_zone:
        trigger = dict(current.get("trigger") or {"type": "time"})
        if cron:
            trigger["cron"] = cron
        if time_zone:
            trigger["time_zone"] = time_zone
        body["trigger"] = trigger
    if targets:
        body["action"] = build_action(*(s.dataset_id(t) for t in targets))
    if enable is not None:
        body["enabled"] = enable
    emit(ctx, s.client.schedules.update(schedule_id, body))


@schedules.command("delete")
@click.argument("schedule_id")
@click.confirmation_option(prompt="Delete this schedule?")
@pass_session
def schedules_delete(s: Session, schedule_id):
    s.client.schedules.delete(schedule_id)
    click.echo("deleted")


@schedules.command("trigger")
@click.argument("schedule_id")
@pass_session
@click.pass_context
def schedules_trigger(ctx, s: Session, schedule_id):
    """Fire the schedule now."""
    emit(ctx, s.client.schedules.trigger(schedule_id))


# -- transforms -----------------------------------------------------------------

@main.group()
def transforms() -> None:
    """Transforms: how a dataset is produced."""


@transforms.command("list")
@click.option("--project", default=None)
@click.option("--output", default=None, help="Only the transforms producing this dataset (ref or id).")
@pass_session
@click.pass_context
def transforms_list(ctx, s: Session, project, output):
    rows = s.client.transforms.list(project_id=s.project_id(project), output=s.dataset_id(output) if output else None)
    emit(ctx, rows, ("id", "name", "type", "output", "updated_at"))


@transforms.command("get")
@click.argument("transform_id")
@pass_session
@click.pass_context
def transforms_get(ctx, s: Session, transform_id):
    emit(ctx, s.client.transforms.get(transform_id))


@transforms.command("set-parameters")
@click.argument("transform_id")
@click.argument("fields", nargs=-1, required=True)
@click.option("--replace", is_flag=True, help="Replace the existing parameters instead of merging.")
@pass_session
@click.pass_context
def transforms_set_parameters(ctx, s: Session, transform_id, fields, replace):
    """Set `config.parameters` from key=value pairs (JSON values accepted)."""
    emit(ctx, s.client.transforms.set_parameters(transform_id, _fields(fields), merge=not replace))


@transforms.command("execute")
@click.argument("transform_id")
@click.option("--branch", default=None)
@pass_session
@click.pass_context
def transforms_execute(ctx, s: Session, transform_id, branch):
    emit(ctx, s.client.transforms.execute(transform_id, branch=branch))


@transforms.command("functions")
@pass_session
@click.pass_context
def transforms_functions(ctx, s: Session):
    """The ready-made transform functions of the platform."""
    emit(ctx, s.client.transforms.functions(), ("name", "label", "description"))


# -- repositories ---------------------------------------------------------------

@main.group()
def repositories() -> None:
    """Repositories: the code, and the lineage scan."""


@repositories.command("list")
@click.option("--project", default=None)
@pass_session
@click.pass_context
def repositories_list(ctx, s: Session, project):
    emit(ctx, s.client.repositories.list(project_id=s.project_id(project)), ("id", "alias", "name", "configuration", "updated_at"))


@repositories.command("get")
@click.argument("repository_id")
@pass_session
@click.pass_context
def repositories_get(ctx, s: Session, repository_id):
    emit(ctx, s.client.repositories.get(repository_id))


@repositories.command("scan")
@click.argument("repository_id")
@click.option("--ref", default=None, help="Git ref to scan (default: the default branch).")
@click.option("--wait/--no-wait", default=True, show_default=True)
@click.option("--timeout", default=600, show_default=True, type=float)
@pass_session
@click.pass_context
def repositories_scan(ctx, s: Session, repository_id, ref, wait, timeout):
    """Scan the code for producer declarations and sync the lineage."""
    emit(ctx, s.client.repositories.scan_lineage(repository_id, ref=ref, wait=wait, timeout=timeout))


@repositories.command("tree")
@click.argument("repository_id")
@click.option("--ref", default=None)
@click.option("--path", default=None)
@pass_session
@click.pass_context
def repositories_tree(ctx, s: Session, repository_id, ref, path):
    emit(ctx, s.client.repositories.tree(repository_id, ref=ref, path=path))


# -- queries, lineage, connections, misc ---------------------------------------

@main.group()
def queries() -> None:
    """Stored SQL queries."""


@queries.command("list")
@click.option("--project", default=None)
@pass_session
@click.pass_context
def queries_list(ctx, s: Session, project):
    emit(ctx, s.client.queries.list(project_id=s.project_id(project)), RESOURCE_COLUMNS)


@queries.command("get")
@click.argument("query_id")
@pass_session
@click.pass_context
def queries_get(ctx, s: Session, query_id):
    answer = s.client.queries.get(query_id)
    if ctx.obj.json or not isinstance(answer, dict) or "sql" not in answer:
        emit(ctx, answer)
    else:
        click.echo(answer["sql"])


@queries.command("execute")
@click.argument("query_id")
@click.option("--branch", default=None)
@pass_session
@click.pass_context
def queries_execute(ctx, s: Session, query_id, branch):
    emit(ctx, s.client.queries.execute(query_id, branch=branch))


@main.command()
@click.argument("resource")
@click.option("--direction", default=None, type=click.Choice(["upstream", "downstream", "both"]))
@pass_session
@click.pass_context
def lineage(ctx, s: Session, resource, direction):
    """The lineage graph around a dataset (ref or id), a project (slug) or any resource id."""
    if resource.startswith("res."):
        resource_id = resource
    elif "." in resource:
        resource_id = s.dataset_id(resource)
    else:
        resource_id = s.project_id(resource)
    if resource_id.startswith("res.project."):
        emit(ctx, s.client.lineage.project(resource_id))
    else:
        emit(ctx, s.client.lineage.graph(resource_id, direction=direction))


@main.group()
def connections() -> None:
    """Connections: the project's data sources."""


@connections.command("list")
@click.option("--project", default=None)
@pass_session
@click.pass_context
def connections_list(ctx, s: Session, project):
    emit(ctx, s.client.connections.list(project_id=s.project_id(project)), RESOURCE_COLUMNS)


@connections.command("get")
@click.argument("connection_id")
@pass_session
@click.pass_context
def connections_get(ctx, s: Session, connection_id):
    emit(ctx, s.client.connections.get(connection_id))


@connections.command("files")
@click.argument("connection_id")
@click.option("--path", default=None)
@click.option("--glob", "pattern", default=None)
@pass_session
@click.pass_context
def connections_files(ctx, s: Session, connection_id, path, pattern):
    emit(ctx, s.client.connections.list_files(connection_id, path=path, glob=pattern), ("path", "size", "modified_at"))


@main.command()
@click.argument("q")
@click.option("--project", default=None)
@click.option("--type", "resource_type", default=None, help="dataset, repository, schedule, transform...")
@pass_session
@click.pass_context
def search(ctx, s: Session, q, project, resource_type):
    """Find resources by name."""
    emit(ctx, s.client.filesystem.search(q, project_id=s.project_id(project), type=resource_type), ("id", "alias", "name", "object"))


@main.group()
def models() -> None:
    """Inference models, and the catalog's ML models (`models ml ...`)."""


@models.command("list")
@pass_session
@click.pass_context
def models_list(ctx, s: Session):
    """The inference models available."""
    emit(ctx, s.client.models.list(), ("id", "object", "owned_by"))


@models.command("ml")
@click.option("--project", default=None)
@pass_session
@click.pass_context
def models_ml(ctx, s: Session, project):
    """The ML models of the catalog."""
    emit(ctx, s.client.ml_models.list(project_id=s.project_id(project)), ("id", "alias", "name", "framework", "task", "version"))


@main.group()
def organizations() -> None:
    """Organizations and their members."""


@organizations.command("list")
@pass_session
@click.pass_context
def organizations_list(ctx, s: Session):
    emit(ctx, s.client.organizations.list(), ("id", "name", "updated_at"))


@organizations.command("members")
@click.argument("organization_id")
@pass_session
@click.pass_context
def organizations_members(ctx, s: Session, organization_id):
    emit(ctx, s.client.organizations.members(organization_id), ("id", "email", "role"))


@main.group("api-keys")
def api_keys() -> None:
    """API keys of a project."""


@api_keys.command("list")
@click.option("--project", default=None)
@pass_session
@click.pass_context
def api_keys_list(ctx, s: Session, project):
    emit(ctx, s.client.api_keys.list(project_id=s.project_id(project)), ("id", "name", "scopes", "created_at"))


@api_keys.command("create")
@click.option("--project", required=True)
@click.option("--name", required=True)
@click.option("--scope", "scopes", multiple=True)
@pass_session
@click.pass_context
def api_keys_create(ctx, s: Session, project, name, scopes):
    """Create a key; the secret is shown once."""
    emit(ctx, s.client.api_keys.create(name=name, project_id=s.project_id(project), scopes=list(scopes) or None))


@api_keys.command("delete")
@click.argument("api_key_id")
@click.confirmation_option(prompt="Revoke this key?")
@pass_session
def api_keys_delete(s: Session, api_key_id):
    s.client.api_keys.delete(api_key_id)
    click.echo("deleted")


def run() -> None:  # pragma: no cover - console entry point with a friendlier error
    try:
        main(standalone_mode=True)
    except GwenlakeException as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
