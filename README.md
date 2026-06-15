# Gwenlake Python Library

The Gwenlake Python library provides convenient access to the Gwenlake API
from applications written in Python. A single `Gwenlake` client gives you access
to your catalog — projects, datasets, files and SQL.

## Installation

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
import gwenlake

# uses GWENLAKE_API_KEY, or the default ~/.gwenlake/credentials profile
client = gwenlake.Gwenlake()

# or pass the key explicitly
client = gwenlake.Gwenlake(api_key="sk-...")

# or pick a profile from ~/.gwenlake/credentials
client = gwenlake.Gwenlake(profile="myteam")
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

## Async

Every resource is also available on `AsyncGwenlake`:

```python
import asyncio
import gwenlake

async def main():
    client = gwenlake.AsyncGwenlake()
    print(await client.projects.list())

asyncio.run(main())
```

See [`examples/`](examples/) for runnable scripts.
