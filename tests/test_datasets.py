import context
import pandas as pd
import gwenlake


client = gwenlake.Client()

resp = client.datasets.list("gwenlake")
print(pd.DataFrame(resp))

resp = client.datasets.get("gwenlake/csrd")
print(resp)

query = {
    "query": "anything about India?s",
    "top_k": 100,
    "threshold": 0.3
}
resp = client.datasets.search("gwenlake/csrd", query=query)
print(pd.DataFrame(resp))
