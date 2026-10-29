# Gwenlake Python Library

The Gwenlake Python library gives applications written in Python access to the
Gwenlake APIs (inference: models, chat completions, embeddings) and to
**Gwenlake Atlas**, the data platform: projects, datasets, files, SQL,
transforms, builds, schedules, lineage, repositories, models, agents. One
`Gwenlake` client wraps every resource behind one authenticated transport, and
the `gwenlake` command (alias `gwl`) offers the same from the terminal.

## Installation

```sh
pip install -U gwenlake
```

Or install the latest development version straight from GitHub:

```sh
pip install -U git+https://github.com/gwenlake/gwenlake-python
```

## Authentication

The client authenticates with a Bearer token, resolved in this order:

1. an explicit `api_key` / `credentials` passed to the client,
2. a named `profile`,
3. the `GWENLAKE_API_KEY` environment variable,
4. the `default` profile in `~/.gwenlake/credentials`.

```bash
export GWENLAKE_API_KEY='sk-...'
```

```python
from gwenlake import Gwenlake

# uses GWENLAKE_API_KEY, or the default ~/.gwenlake/credentials profile
client = Gwenlake()

# or pass the key explicitly
client = Gwenlake(api_key="sk-...")

# or pick a profile from ~/.gwenlake/credentials
client = Gwenlake(profile="myteam")
```

The `~/.gwenlake/credentials` file is an INI file with one section per profile,
holding either a static `token` (API key) or OAuth2 `client_id` / `client_secret`.

## Projects

```python
projects = client.projects.list()
for p in projects:
    print(p["alias"], p["id"])

project = client.projects.get("res.project.…")
```

## Datasets

```python
datasets = client.datasets.list()
for d in datasets:
    print(d["alias"], d["id"])

dataset = client.datasets.get("res.dataset.…")
```

## Files

Files live inside a dataset.

```python
dataset_id = "res.dataset.…"

# list files
for f in client.files.list(dataset_id):
    print(f["filename"], f["file_size"])

# upload a local file (optionally into a subdirectory with path=...)
client.files.upload(dataset_id, "report.pdf")
client.files.upload(dataset_id, "report.pdf", path="docs")

# download a file
content = client.files.download(dataset_id, "report.pdf")

# presigned URL / delete
url = client.files.presigned_url(dataset_id, "report.pdf")
client.files.delete(dataset_id, "report.pdf")
```

## SQL

Run SQL against a dataset (DuckDB), referencing it as
`'<project_alias>.<dataset_alias>'`. With `format="json"` the rows are returned
under `data`:

```python
result = client.statements.create(
    statement="SELECT * FROM 'flights.flight-data' LIMIT 10",
    format="json",
)
for row in result["data"]:
    print(row)
```

Pass a `connection_id` to run the statement against a connection's native engine
(PostgreSQL, S3, …) instead of a dataset.

### Read a result whole, export it

`statements.create` answers one request, capped at 1000 rows unless the
statement carries its own `LIMIT`. To read a result whole, the library pages
it (`LIMIT`/`OFFSET` around your statement) and gives it back as Arrow, as a
DataFrame, or written to a file whose format follows its extension:

```python
table = client.statements.read_all("SELECT * FROM 'fleetsight.aisdk_positions' WHERE zone = 'brest'")
df = client.statements.to_dataframe("SELECT * FROM 'fleetsight.aisdk_vessels'")

client.statements.to_file("SELECT * FROM 'fleetsight.aisdk_positions'", "positions.parquet")
client.statements.to_file("SELECT mmsi, name FROM 'fleetsight.aisdk_vessels'", "vessels.csv")
client.statements.to_file("SELECT * FROM 'fleetsight.aisdk_vessels'", "vessels.jsonl")   # or .json, one array

for page in client.statements.iter_arrow("SELECT * FROM 'fleetsight.aisdk_positions'", page_rows=100_000):
    ...   # pyarrow.Table, 100 000 rows at a time
```

## Atlas resources

Every route of the Atlas catalog has a method, under the resource it belongs
to. Datasets are referred to by id, or by `"<project>.<dataset>"` through
`client.resolve(ref)`.

| Attribute | Covers |
| --- | --- |
| `client.projects`, `client.filesystem` | projects, folders, search, move/rename/restore of any resource |
| `client.datasets`, `client.files` | datasets (create, update, summary, branches, `delete_rows`, maintenance, search) and their files |
| `client.statements`, `client.queries` | ad hoc SQL, stored SQL queries and their versions |
| `client.transforms` | the producers of the lineage (`set_parameters`, `execute`, `functions`) |
| `client.builds` | builds (`run`, `wait`, `run_and_wait`, `logs`, `cancel`) and asynchronous tasks |
| `client.schedules` | cron schedules (`time_trigger`, `build_action`, `trigger`, `enable`) |
| `client.lineage` | the lineage graph, data branches of a lineage cone, workflow positions |
| `client.repositories` | repositories, `scan_lineage`, and the git routes (tree, file, commit, branches) |
| `client.connections` | connections, their files, `query`, `test`, credentials |
| `client.ml_models`, `client.mediasets`, `client.syncs`, `client.flows` | ML models, mediasets, syncs, flows |
| `client.agents`, `client.skills`, `client.tools`, `client.ontologies`, `client.applications` | agents and what they use |
| `client.organizations`, `client.users`, `client.api_keys` | the tenant, you, the keys |

```python
dataset = client.resolve("fleetsight.aisdk_positions")

batch = client.builds.run_and_wait(dataset, target_only=True)       # build it, follow it
print(client.builds.logs(batch["builds"][-1]["id"])["logs"])

from gwenlake.schedules import build_action, time_trigger
client.schedules.create({"name": "Nightly refresh", "project_id": project_id,
                         "trigger": time_trigger("0 6 * * *", "Europe/Paris"),
                         "action": build_action(dataset), "enabled": True})

scan = client.repositories.scan_lineage(repository_id, wait=True)    # re-read the code's producers
print(scan["result"]["transforms_found"], scan["result"]["warnings"])

client.transforms.set_parameters(transform_id, {"listen_seconds": 600})
```

`tests/test_openapi_coverage.py` checks that every route of the catalog's
OpenAPI description has a method; a route left out on purpose is listed there.

## Command line

Installing the library adds `gwenlake` (and the shorter `gwl`): the same
resources in noun-verb form, printing tables or, with `--json`, the API's answer.

```sh
gwenlake me
gwenlake projects list
gwenlake datasets list --project fleetsight
gwenlake datasets summary fleetsight.aisdk_positions
gwenlake sql "SELECT zone, count(*) FROM 'fleetsight.aisstream_positions' GROUP BY 1"
gwenlake sql "SELECT * FROM 'fleetsight.aisdk_vessels'" --out vessels.parquet       # or .csv, .json, .jsonl
gwenlake datasets export fleetsight.aisdk_positions --out positions.csv --where "zone = 'brest'"
gwenlake builds run fleetsight.aisstream_vessels --wait
gwenlake builds logs build.58d2bddbad62
gwenlake schedules create --project fleetsight --name "Nightly" --cron "0 6 * * *" --time-zone Europe/Paris --target fleetsight.aisdk_quality_by_day
gwenlake repositories scan res.repository.… --wait
gwenlake transforms set-parameters res.transform.… listen_seconds=600
gwenlake files upload fleetsight.aisdk_positions_raw day.parquet --mode APPEND
```

Credentials: `--api-key`, `--profile NAME` (a section of `~/.gwenlake/credentials`),
`GWENLAKE_API_KEY` (a `.env` in the current directory is read), or the `default`
profile. The endpoint is `--base-url`, `GWENLAKE_BASE_URL`, or the profile's
`base_url`, which is how a tenant deployed on its own host is reached:

```sh
gwenlake config set-profile acme --token sk-... --base-url https://atlas.acme.example/v1
gwenlake --profile acme datasets list
gwenlake config list        # the profiles, secrets masked
```

`gwenlake <resource> --help` lists the commands of a resource.

## Transforms

A transforms layer (`gwenlake.transforms`) lets you write
dataset-to-dataset transformations as decorated functions. Datasets (and
models) are addressed as `"<project_alias>.<alias>"` — the same handle used in
SQL.

`transform_df` — the function receives each `Input` as a `pandas.DataFrame` and
**returns** the DataFrame to write to the (single) `Output`. The result is
written automatically (snapshot/replace by default):

```python
from gwenlake.transforms import transform_df, Input, Output

@transform_df(
    raw_data=Input("Project_A.users"),
    processed_data=Output("Project_A.users_filtered"),
)
def process(raw_data):
    df = raw_data[raw_data["age"] >= 18].copy()
    df["name_upper"] = df["name"].str.upper()
    return df

process(client)   # reads, computes, writes
```

With several `Output`s, return a dict keyed by their keyword names; each
DataFrame is written to the matching dataset:

```python
@transform_df(
    raw=Input("Project_A.contacts"),
    valid=Output("Project_A.contacts_valid"),
    rejected=Output("Project_A.contacts_rejected"),
)
def split(raw):
    ok = raw["email"].str.contains("@")
    return {"valid": raw[ok], "rejected": raw[~ok]}
```

`transform` — the lower-level form: the function receives `TransformInput` /
`TransformOutput` objects and reads/writes explicitly. Use it for non-tabular
data (images, PDFs, …) via `.filesystem()`:

```python
from gwenlake.transforms import transform, Input, Output

@transform(
    my_input=Input("Project_A.users"),
    my_output=Output("Project_A.users_distinct"),
)
def dedupe_users(my_input, my_output):
    df = my_input.dataframe()
    # mode="replace" (default) clears the dataset first; "append" keeps existing files
    my_output.write_dataframe(df.drop_duplicates(), mode="replace")

@transform(
    images=Input("Project_A.scans"),
    thumbnails=Output("Project_A.scans_processed"),
)
def process_files(images, thumbnails):
    src, dst = images.filesystem(), thumbnails.filesystem()
    for entry in src.ls():
        data = src.read(entry["filename"])          # raw bytes (PDF, image, …)
        with dst.open(f"copy/{entry['filename']}", "wb") as f:
            f.write(data)
```

### Connections

A **connection** is a datasource a project declares once (an SMB share, a
bucket, a SharePoint library). A `file` sync copies what it holds into a
dataset; a transform that declares the connection as a `Connection(...)` input
reads it **itself** — walks the directory, picks the files it wants, lays its
output out as it likes. `.filesystem()` is read-only and goes through the
catalog as the build's own identity, so the connection's credentials never
reach the code:

```python
import shutil
from gwenlake.transforms import transform, Connection, Output

@transform(
    share=Connection("Ops.drop-folder"),          # "<project>.<connection slug>"
    out=Output("Ops.collected"),
)
def collect(share, out):
    fs_in, fs_out = share.filesystem(), out.filesystem()
    for f in fs_in.ls(glob="**/*.pdf"):           # f["path"] = "2024/q3/report.pdf"
        with fs_in.open(f["path"], "rb") as src, fs_out.open(f["path"], "wb") as dst:
            shutil.copyfileobj(src, dst)
```

`ls(path=, glob=)` lists recursively (paths relative to the connection's root;
`*` stays within a directory, `**` descends — the same rule as a sync's
`path_glob`), `read(path)` / `open(path, "rb")` fetch one file. The dataset
`FileSystem.ls` takes the same `glob=` so an output can be walked the same way.
The catalog scanner reads `Connection(...)` like `Input(...)`, so the lineage
shows the connection feeding the output. `client.connections` exposes the
same calls directly (`list`, `get`, `list_files`, `iter_files`, `download`).

### Incremental transforms

A transform that must not redo what it has already done keeps its memory in
one of its **own Outputs** — a log of the files it has processed — and reads
it back on the next run. An Output can never be an Input of the same
transform (that is a cycle in the lineage), so `@incremental` — stacked
above `@transform` / `@transform_df` — gives the Output a `"previous"`
reading mode and makes writes **add** to it:

```python
import pandas as pd
from gwenlake.transforms import incremental, transform, Connection, Output

@incremental(semantic_version=1)
@transform(
    share=Connection("Ops.drop-folder"),
    pages=Output("Ops.pages"),
    log=Output("Ops.processed"),
)
def ingest(share, pages, log):
    done = set(log.dataframe("previous", schema=["path"])["path"])   # empty on the first run
    new = [f for f in share.filesystem().ls(glob="**/*.pdf") if f["path"] not in done]
    if not new:
        return
    pages.write_dataframe(parse(new))                                  # appended
    log.write_dataframe(pd.DataFrame({"path": [f["path"] for f in new]}))   # last: a failure re-processes, never forgets
```

`dataframe("previous", schema)` is the output as the last successful run left
it (read it **before** the run's first write; an empty frame of `schema` while
there is none), `dataframe("current")` re-reads it, `filesystem("previous")`
is the same for files. Writes default to `modify` (`set_mode("replace")` or
`mode="replace"` snapshots instead). Bump `semantic_version` to start over on
the next build. An **Iceberg** input also answers `dataframe("added")` inside a build — the
rows appended since the last successful run, read from the table's own
snapshot history up to the point pinned before the run — and
`dataframe("previous")`, the table as the last run saw it. A files dataset or
a connection keeps no history: those are always read whole, and `"added"` is
refused rather than quietly answered with everything — the log Output is what
remembers. A table rewritten in between (snapshot, delete, upsert) has no
delta either; the catalog says so, and the run reads it whole or bumps
`semantic_version`.

### Models

A **model** is a catalog resource whose artifacts live in the git repository the
code lives in (`/models` in the catalog). `train` produces one, and `Model(...)`
binds one a transform loads — conventionally as `model=`:

```python
import joblib
from gwenlake.transforms import train, transform_df, Input, Model, Output

@train(
    training_set=Input("Project_A.churn_training"),
    output=Output("Project_A.churn"),          # an Output of @train is a MODEL
)
def fit(training_set, output):
    clf = fit_classifier(training_set)         # training_set is a DataFrame
    joblib.dump(clf, output.file("model.pkl")) # write under the model's directory
    return {"auc": 0.91}                       # returned dict -> the model's metrics

@transform_df(
    customers=Input("Project_A.customers"),
    model=Model("Project_A.churn"),            # a model this transform loads
    output=Output("Project_A.churn_scores"),
)
def predict(customers, model):
    clf = joblib.load(model.file("model.pkl"))
    return customers.assign(churn=clf.predict(customers))
```

Models are a catalog resource served by api-catalog. Its `/models` endpoints
are **not** routed through the public gateway today (that path serves the
inference model list), so `model.info()` / `model.update()` work from inside a
build — where the client already points at api-catalog — but not against
`api.gwenlake.com`. `model.path` never needs an API call during a build.

`output.path` (and `model.path`) is the model's directory **in the checkout**:
during a build the engine sets it, commits whatever the training run wrote
there, and pins that commit as the model's version. `model.parameters`,
`model.version` and `model.update(metrics=..., version=...)` cover the model
card. Lineage follows: `datasets -> train -> model -> transform -> dataset`.

**Large datasets** — page through with `LIMIT/OFFSET` instead of loading
everything at once. `iter_dataframes()` yields `pandas.DataFrame` chunks and
`write_dataframes()` streams them back out as `part-00000.parquet`, …:

```python
@transform(
    big_dataset=Input("Project_A.events"),
    result=Output("Project_A.events_clean"),
)
def transform_in_chunks(big_dataset, result):
    chunks = (
        chunk[chunk["valid"]]
        for chunk in big_dataset.iter_dataframes(chunk_size=50_000, order_by="id")
    )
    result.write_dataframes(chunks, mode="replace")
```

Pass `order_by=` for a deterministic page split. The transforms layer is
synchronous.

## Async

Every resource is also available on `AsyncGwenlake`:

```python
import asyncio
from gwenlake import AsyncGwenlake

async def main():
    client = AsyncGwenlake()
    print(await client.projects.list())

asyncio.run(main())
```

See [`examples/`](examples/) for runnable scripts.
