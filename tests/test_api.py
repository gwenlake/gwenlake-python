import context
import pandas as pd
import gwenlake

client = gwenlake.api.APIClient()
resp = client.list_models()
print(pd.DataFrame(resp))

documents = [
    "test de texte 1",
    "test de texte 2",
    "test de texte 3",
]

resp = client.embed_documents(documents)
print(pd.DataFrame(resp))

# print(len(resp[0]["embedding"]))
