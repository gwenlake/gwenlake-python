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
    donnees_brutes=Input("Projet_A.utilisateurs"),
    donnees_nettoyees=Output("Projet_A.utilisateurs_filtres"),
)
def ma_transformation(donnees_brutes):
    df = donnees_brutes
    majeurs = df[df["age"] >= 18].copy()
    majeurs["nom_majuscule"] = majeurs["nom"].str.upper()
    return majeurs


# 2) transform: the body receives TransformInput/TransformOutput objects and
#    reads/writes explicitly. Works for tabular data...
@transform(
    mon_entree=Input("Projet_A.utilisateurs"),
    mon_sortie=Output("Projet_A.utilisateurs_distinct"),
)
def transformation_avancee(mon_entree, mon_sortie):
    df = mon_entree.dataframe()
    df_resultat = df.drop_duplicates()
    # mode="replace" (defaut) vide le dataset avant d'ecrire (snapshot facon
    # Foundry) ; mode="append" ajoute le fichier sans rien supprimer.
    mon_sortie.write_dataframe(df_resultat, mode="replace")


# 3) ...and for raw files (images, PDFs, anything non-tabular) via .filesystem().
@transform(
    images=Input("Projet_A.scans"),
    vignettes=Output("Projet_A.scans_traites"),
)
def traiter_fichiers(images, vignettes):
    src = images.filesystem()
    dst = vignettes.filesystem()
    for entry in src.ls():
        name = entry["filename"]
        data = src.read(name)
        # ... process the bytes (PDF, image, ...) ...
        with dst.open(f"copie/{name}", "wb") as f:
            f.write(data)


# 4) Large datasets: page through with LIMIT/OFFSET instead of loading it all.
#    iter_dataframes() yields DataFrame chunks; write_dataframes() streams them
#    back out as part-00000.parquet, part-00001.parquet, ... (replace clears the
#    output once up front). Pass order_by= for a guaranteed-deterministic split.
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


if __name__ == "__main__":
    ma_transformation(client)
    transformation_avancee(client)
    traiter_fichiers(client)
    transformation_par_chunks(client)
