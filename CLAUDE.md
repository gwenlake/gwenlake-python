# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`gwenlake` is the Python client SDK for the Gwenlake API. A single `Gwenlake` client (and `AsyncGwenlake`) wraps every resource — **inference** (models, chat completions, embeddings) and **catalog/factory** (datasets, files, projects) — behind one authenticated HTTP transport. `src/`-layout package built with the `uv_build` backend, Python >= 3.12.

## Commands

This project uses **uv**.

```sh
uv sync                          # create venv and install deps + the package (editable)
uv run gwenlake --help           # CLI entrypoint (gwenlake.cli:main)
uv run gwenlake models           # e.g. list models for the default profile
uv run python examples/chat.py   # run an example script
uv build                         # build sdist + wheel
```

No test suite, linter, or formatter config in the repo. Releases publish to PyPI via `.github/workflows/python-publish.yml` on a published GitHub Release; version lives in `pyproject.toml` and is read at runtime via `importlib.metadata`.

> **macOS + iCloud gotcha (`ModuleNotFoundError: gwenlake`):** this repo lives under `~/Documents`, which iCloud Drive syncs and which sets the macOS `hidden` file flag on files in `.venv`. Python 3.13's `site` module **skips hidden `.pth` files**, so the editable install's `gwenlake.pth` is ignored and the package vanishes — intermittently, since reinstalling clears the flag until iCloud re-applies it. Durable fix: put the venv **outside** iCloud, e.g. `export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/gwenlake-python"` then `uv sync` (and use `uv run` with that env var set). Quick one-off unblock: `chflags nohidden .venv/lib/python*/site-packages/*.pth`.

## Architecture

### Flat module layout

Everything lives directly under `src/gwenlake/` — there are **no `auth/`, `inference/`, or `factory/` subpackages** (they were flattened). One module per concern: `client.py`, `credentials.py`, `flow.py`, `token.py`, `models.py`, `chat.py`, `embeddings.py`, `datasets.py`, `files.py`, `projects.py`, plus `types.py`, `constants.py`, `exceptions.py`, `cli.py`.

### Single gateway, one base URL

The `Gwenlake` client talks to one gateway (default `https://api.gwenlake.com/v1`, override via `base_url=` or `GWENLAKE_BASE_URL`). **Every** resource — inference (`models`, `chat`, `embeddings`) and catalog (`datasets`, `files`, `projects`, `statements`) — is served under `/v1`, so the base URL carries the version and **resource paths are version-agnostic** (`/models`, `/chat/completions`, `/datasets`, `/filesystem/projects`, `/sql/statements`). httpx preserves the `/v1` base path when joining a leading-slash path, so don't repeat `/v1` in resource URLs. Verified live: `/v1/models`, `/v1/datasets`, `/v1/filesystem/projects` all 200; the same paths without `/v1` are 404.

The real catalog backend is the FastAPI service at `/Users/sylbarth/Documents/platform/api-catalog`; its full route map is in the project memory `api-catalog-endpoints` — consult it before adding/changing catalog paths. Catalog **list** endpoints return an envelope `{"object":"list","data":[...]}`, so list methods return `.json()["data"]`; `get`/`create` return the object directly. Resource ids are typed strings (`res.project.…`, `res.dataset.…`); the dataset/project `alias` is the human-friendly handle used in SQL (`FROM '<project_alias>.<dataset_alias>'`).

### Client construction & unified auth (`client.py`, `credentials.py`)

`gwenlake.Gwenlake` / `gwenlake.AsyncGwenlake` and `gwenlake.Credentials` are the only public exports. `Gwenlake(...)` resolves credentials via `_resolve_credentials` in this order: explicit `credentials=` → `api_key=` (wrapped as a static token) → `profile=` → `GWENLAKE_API_KEY` env → the `default` profile in `~/.gwenlake/credentials`. Raises `GwenlakeException` if none usable.

`Credentials` supports two auth modes, both yielding a Bearer token in the `Authorization` header:
- **Static token / API key** — `Credentials(token=...)`. The common path; what `api_key=` produces.
- **OAuth2 client-credentials** — `Credentials(client_id=, client_secret=, token_uri=)`; `ClientOAuthFlowProvider` (`flow.py`) fetches/refreshes tokens against Keycloak (`auth.gwenlake.com`, realm `gwenlake-api`), with a daemon thread refreshing 60s before expiry.

`Credentials.from_profile(name)` reads the INI file at `~/.gwenlake/credentials` (`%APPDATA%/.gwenlake/credentials` on Windows); each section is a profile with `token` or `client_id`/`client_secret`/`scopes`/`hostname`. Returns `None` if the file/section is missing. `Credentials.is_configured` tells whether it can produce a token.

### Transport layer (`client.py`)

The high-level `Gwenlake` client and the low-level transport live in the **same file** (`client.py`): transport classes (`BaseApiClient`, `ApiClient`, `AsyncApiClient`, `RequestOptions`) are defined first, then resource modules are imported, then `Gwenlake`/`AsyncGwenlake` — this ordering is what keeps the resource ↔ client imports from cycling, so keep new transport definitions above the resource imports.

Resource request flow:
1. Build a **`RequestOptions`** (pydantic). Real fields: `method`, `url`, `path_params`, `params`, `headers`, `json_data`, `files`, `max_retries`, `timeout`, `follow_redirects`. (No `path`, `body`, or `data` — those were bugs that have been fixed.)
2. `client.send(request_info)` → httpx `Response`; the caller does `.raise_for_status()` then `.json()` / `.content`. `client.stream(request_info)` yields raw lines for streaming.
3. `_create_headers` always injects `User-Agent` and `Authorization: Bearer <token>` from `credentials.get_token().access_token`.

### Resources

Resources wired onto the client: `models`, `chat`, `embeddings`, `datasets`, `files`, `projects`, `statements`. Each is a thin class holding `_client`, with a **sync + `Async` pair** of identical bodies (`Chat`/`AsyncChat`, `Datasets`/`AsyncDatasets`, …). When you change one method, update its async twin. Catalog list methods return `.json()["data"]`; inference chat/models return raw dicts, `embeddings.create` returns a typed `EmbeddingResponse` (batched in chunks of `BATCH_SIZE=100`). `types.py` holds the pydantic response models — the layer is only partially typed.

File ops (`files.py`) map to the catalog's S3-backed routes: `list(dataset_id, path=)`, `download(dataset_id, filepath)→bytes`, `upload(dataset_id, file, path=, filename=)` (multipart, accepts a local path or raw bytes), `presigned_url(...)`, `delete(...)`. There is no `/content` or `/upload` suffix — uploads POST to `/datasets/{id}/files[/{path}]`. `statements.create(statement=, connection_id=, format="json", ...)` runs SQL via `POST /sql/statements`; without `connection_id` it's dataset mode (`FROM '<project_alias>.<dataset_alias>'`, DuckDB) and `format="json"` returns rows under `data` — not every dataset is queryable (non-tabular ones return 403 "Cannot query this dataset").

### CLI (`cli.py`)

`click`-based, entrypoint `gwenlake = gwenlake.cli:main`. `--profile` builds a `Gwenlake(profile=...)`; subcommands (`models`, `datasets`, `projects`) print JSON. `click` is a declared dependency.
