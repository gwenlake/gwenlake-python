"""List projects, then datasets, then files of a dataset, then run a SQL query.

Uses the default credentials: the GWENLAKE_API_KEY environment variable, or the
``default`` profile in ~/.gwenlake/credentials.
"""

import httpx

import gwenlake

client = gwenlake.Gwenlake()  # default credentials

# 1) Projects
projects = client.projects.list()
print("Projects:")
for p in projects:
    print(f"  - {p['alias']:30} {p['id']}")

# project id -> alias, to resolve a dataset's parent project below
project_alias = {p["id"]: p["alias"] for p in projects}

# 2) Datasets
datasets = client.datasets.list()
print("\nDatasets:")
for d in datasets:
    print(f"  - {d['alias']:30} {d['id']}  (type={d.get('type')})")

# 3) + 4) Files and a SQL query, on the first dataset we can actually query.
#    In dataset mode the query runs through DuckDB and references
#    FROM '<project_alias>.<dataset_alias>'. Not every dataset is queryable
#    (e.g. non-tabular ones), so we try until one succeeds.
for d in datasets:
    table = f"{project_alias.get(d.get('parent_id'))}.{d['alias']}"
    try:
        result = client.statements.create(
            statement=f"SELECT * FROM '{table}' LIMIT 5",
            format="json",
        )
    except httpx.HTTPStatusError:
        continue

    print(f"\nFiles in dataset {d['alias']} ({d['id']}):")
    for f in client.files.list(d["id"]):
        print(f"  - {f.get('filename', f)}  ({f.get('file_size')} bytes)")

    print(f"\nSQL: SELECT * FROM '{table}' LIMIT 5")
    for row in result.get("data", []):
        print(f"  {row}")
    break
else:
    print("\nNo queryable dataset found.")
