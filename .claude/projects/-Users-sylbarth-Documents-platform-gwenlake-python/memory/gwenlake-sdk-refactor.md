---
name: gwenlake-sdk-refactor
description: Design decisions for the unified gwenlake-python SDK client (single Client, flat layout, gateway base URL)
metadata:
  type: project
---

The `gwenlake-python` SDK was refactored (June 2026) from two clients (`InferenceClient` + `FactoryClient`) into a single unified `gwenlake.Gwenlake` / `AsyncGwenlake` client (the class is named `Gwenlake`, not `Client`).

**Why:** the user wanted one universal client covering models, embeddings, datasets, projects, files, etc., with unified authentication.

**How to apply:**
- **Flat layout:** everything lives directly under `src/gwenlake/` — no `auth/`, `inference/`, `factory/` subpackages (explicitly removed at the user's request).
- **One file for the client:** the high-level `Client`/`AsyncClient` AND the low-level transport (`ApiClient`, `AsyncApiClient`, `RequestOptions`) all live in `client.py` (renamed from `api_client.py`). Transport is defined first, resources imported after, `Client` last — this ordering avoids the resource↔client import cycle.
- **Single gateway:** one `base_url` = `https://api.gwenlake.com/v1` (the gateway serves EVERYTHING — inference AND catalog — under `/v1`; verified live). Resource paths are version-agnostic (`/models`, `/datasets`, `/filesystem/projects`, `/sql/statements`); don't repeat `/v1`. See [[api-catalog-endpoints]] for catalog routes and [[icloud-pth-modulenotfound]] for the venv gotcha.
- **Unified auth:** `Credentials` supports static token (api key) OR OAuth2 client-credentials; `from_profile` reads `~/.gwenlake/credentials` INI. `Client` resolves: explicit credentials → api_key → profile → `GWENLAKE_API_KEY` env → `default` profile.
- **Public exports** (`__init__.py`): only `Gwenlake`, `AsyncGwenlake`, `Credentials`.
- Resource scope implemented: models, chat, embeddings, datasets, files, projects, statements (SQL via `/sql/statements`). Catalog has many more (agents, connections, repositories, organizations, apikeys, schedules, orchestration) ready to add following the same pattern. Working end-to-end example: `examples/catalog.py` (projects → datasets → files → SQL).

The original SDK code had transport-contract bugs (resources passing `path=`/`body=`/`data=` instead of `url=`/`json_data=`, a nonexistent `call_api`) — all fixed during the refactor. The README/`examples/` still reference aspirational features not implemented (`prompts`, `textgeneration`).
