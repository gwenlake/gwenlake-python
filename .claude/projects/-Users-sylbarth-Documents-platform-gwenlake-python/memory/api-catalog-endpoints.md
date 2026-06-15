---
name: api-catalog-endpoints
description: HTTP endpoint map of the api-catalog microservice (factory/catalog API the gwenlake-python SDK targets for datasets, projects, files, etc.)
metadata:
  type: reference
---

The **api-catalog** FastAPI microservice lives at `/Users/sylbarth/Documents/platform/api-catalog` (routers in `app/routers/*.py`, schemas in `app/schemas/*.py`). It is the catalog/factory backend the `gwenlake-python` SDK calls for non-inference resources. Inference (models/chat/embeddings) is a **separate** service.

**Auth:** Bearer token in `Authorization: Bearer <token>` header — either a Keycloak OAuth2 JWT or an API key prefixed `sk_`. `GET /auth` validates the token. The catalog *service itself* mounts routes at root (`/datasets`, `/filesystem/projects`, ...), but the **public gateway `https://api.gwenlake.com` serves EVERYTHING under `/v1`** — verified live: `/v1/datasets`, `/v1/filesystem/projects`, `/v1/models` → 200; the same without `/v1` → 404. So the SDK uses `base_url=https://api.gwenlake.com/v1` and version-agnostic paths. Catalog list endpoints return `{"object":"list","data":[...]}`. Resource ids are typed (`res.project.…`/`res.dataset.…`); `alias` is the SQL handle.

**Resource IDs** are typed strings like `res.dataset.xxx` (not `org/name` path-style as the SDK README implies).

Key endpoints (method — path — note):
- **Datasets** `/datasets`: GET list, POST create (`DatasetUpdate`: name, project_id, type="files", description), GET/PATCH/DELETE `/{dataset_id}`. Query: organization_id, project_id.
- **Dataset files** (S3-backed): GET `/datasets/{id}/files?path=` list; POST `/datasets/{id}/files` upload to root (multipart); POST `/datasets/{id}/files/{path:path}` upload to subdir; GET `/datasets/{id}/files/{filepath:path}` download stream; GET `/datasets/{id}/files/{filepath:path}/presigned-url?expires_in=` ; DELETE `/datasets/{id}/files/{filepath:path}`. **No `/content` or `/upload` suffix.**
- **Projects** live under `/filesystem`: GET `/filesystem/projects` list, GET `/filesystem/projects/{id}`, POST `/filesystem/projects` (`ProjectUpdate`: name, organization_id, description, picture), PATCH (`ResourcePatch`), DELETE. Sub-lists: `/filesystem/projects/{id}/datasets|applications|agents|connections|repositories|schedules`.
- **Filesystem resources** (polymorphic): `/filesystem/resources`, `/filesystem/resources/{id}` (+ `/logo`, `/move`, `/rename`, `/restore`), `/filesystem/search?q=`, `/filesystem/folders`.
- **Api keys** `/api-keys`: GET list/`{id}`, POST (`ApiKeyCreate`: name, project_id → returns plain key once), DELETE.
- **Organizations** `/organizations`: CRUD + `/members`, `/projects`, `/api-keys`.
- **Agents** `/agents`, **Connections** `/connections`, **Repositories** `/repositories`, **Applications** `/applications`, **Schedules** `/schedules` (+ `/trigger`): standard CRUD with organization_id/project_id query filters.
- **Git** `/git/{repository_id}`: `/branches`, `/tree`, `/file`, POST `/commit`, POST `/import`.
- **SQL** `POST /sql/statements` (`StatementsRequest`: statement, connection_id?, format=pyarrow|json|csv, parameters, limit).
- **Orchestration** `/orchestration`: dataset transforms (`PUT/GET/DELETE /datasets/{id}/transform`), `/lineage/{id}`, `/builds`.

See [[gwenlake-sdk-refactor]] for how the SDK wraps these.
