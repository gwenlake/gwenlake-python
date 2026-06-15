# Gwenlake Python Library

The Gwenlake Python library provides convenient access to the Gwenlake API
from applications written in Python. A single `Gwenlake` client gives you access
to your catalog — projects, datasets, files and SQL.

## Installation

```sh
pip install -U gwenlake
```

Or install the latest development version straight from GitHub:

```sh
pip install -U git+https://github.com/gwenlake/gwenlake-python
```

The [Transforms](#transforms) layer needs pandas (and pyarrow for parquet);
install it with the optional `transforms` extra:

```sh
pip install -U "gwenlake[transforms]"
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

## Transforms

A Palantir Foundry-style transforms layer (`gwenlake.transforms`) lets you write
dataset-to-dataset transformations as decorated functions. Datasets are
addressed as `"<project_alias>.<dataset_alias>"` — the same handle used in SQL.
Requires the `transforms` extra (see [Installation](#installation)).

`transform_df` — the function receives each `Input` as a `pandas.DataFrame` and
**returns** the DataFrame to write to the (single) `Output`. The result is
written automatically (snapshot/replace by default):

```python
from gwenlake.transforms import transform_df, Input, Output

@transform_df(
    donnees_brutes=Input("Projet_A.utilisateurs"),
    donnees_nettoyees=Output("Projet_A.utilisateurs_filtres"),
)
def ma_transformation(donnees_brutes):
    df = donnees_brutes[donnees_brutes["age"] >= 18].copy()
    df["nom_majuscule"] = df["nom"].str.upper()
    return df

ma_transformation(client)   # reads, computes, writes
```

`transform` — the lower-level form: the function receives `TransformInput` /
`TransformOutput` objects and reads/writes explicitly. Use it for non-tabular
data (images, PDFs, …) via `.filesystem()`:

```python
from gwenlake.transforms import transform, Input, Output

@transform(
    mon_entree=Input("Projet_A.utilisateurs"),
    mon_sortie=Output("Projet_A.utilisateurs_distinct"),
)
def transformation_avancee(mon_entree, mon_sortie):
    df = mon_entree.dataframe()
    # mode="replace" (default) clears the dataset first; "append" keeps existing files
    mon_sortie.write_dataframe(df.drop_duplicates(), mode="replace")

@transform(
    images=Input("Projet_A.scans"),
    vignettes=Output("Projet_A.scans_traites"),
)
def traiter_fichiers(images, vignettes):
    src, dst = images.filesystem(), vignettes.filesystem()
    for entry in src.ls():
        data = src.read(entry["filename"])          # raw bytes (PDF, image, …)
        with dst.open(f"copie/{entry['filename']}", "wb") as f:
            f.write(data)
```

**Large datasets** — page through with `LIMIT/OFFSET` instead of loading
everything at once. `iter_dataframes()` yields `pandas.DataFrame` chunks and
`write_dataframes()` streams them back out as `part-00000.parquet`, …:

```python
@transform(
    gros_dataset=Input("Projet_A.evenements"),
    resultat=Output("Projet_A.evenements_propres"),
)
def transformation_par_chunks(gros_dataset, resultat):
    chunks = (
        chunk[chunk["valide"]]
        for chunk in gros_dataset.iter_dataframes(chunk_size=50_000, order_by="id")
    )
    resultat.write_dataframes(chunks, mode="replace")
```

Pass `order_by=` for a deterministic page split. The transforms layer is
synchronous.

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
