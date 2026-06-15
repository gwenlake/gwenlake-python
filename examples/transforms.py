"""Foundry-style transforms over the Gwenlake catalog.

Requires the optional pandas/pyarrow extras: ``pip install gwenlake[transforms]``.
Uses the default credentials (GWENLAKE_API_KEY env var or the ``default`` profile).
"""

import gwenlake
from gwenlake.transforms import transform_df, transform, Input, Output

client = gwenlake.Gwenlake()  # default credentials


# 1) transform_df: the body receives Inputs as pandas DataFrames and returns the
#    DataFrame to write to the Output (written automatically).
@transform_df(
    raw_users=Input("Project_A.users"),
    clean_users=Output("Project_A.users_filtered"),
)
def clean_adults(raw_users):
    df = raw_users
    adults = df[df["age"] >= 18].copy()
    adults["name_upper"] = adults["name"].str.upper()
    return adults


# 2) transform: the body receives TransformInput/TransformOutput objects and
#    reads/writes explicitly. Works for tabular data...
@transform(
    my_input=Input("Project_A.users"),
    my_output=Output("Project_A.users_distinct"),
)
def dedupe_users(my_input, my_output):
    df = my_input.dataframe()
    result = df.drop_duplicates()
    # mode="replace" (default) clears the dataset before writing (Foundry-style
    # snapshot); mode="append" adds the file without deleting anything.
    my_output.write_dataframe(result, mode="replace")


# 3) ...and for raw files (images, PDFs, anything non-tabular) via .filesystem().
@transform(
    images=Input("Project_A.scans"),
    thumbnails=Output("Project_A.scans_processed"),
)
def process_files(images, thumbnails):
    src = images.filesystem()
    dst = thumbnails.filesystem()
    for entry in src.ls():
        name = entry["filename"]
        data = src.read(name)
        # ... process the bytes (PDF, image, ...) ...
        with dst.open(f"copy/{name}", "wb") as f:
            f.write(data)


# 4) Large datasets: page through with LIMIT/OFFSET instead of loading it all.
#    iter_dataframes() yields DataFrame chunks; write_dataframes() streams them
#    back out as part-00000.parquet, part-00001.parquet, ... (replace clears the
#    output once up front). Pass order_by= for a guaranteed-deterministic split.
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


if __name__ == "__main__":
    clean_adults(client)
    dedupe_users(client)
    process_files(client)
    transform_in_chunks(client)
