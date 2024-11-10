import context
import gwenlake
import pandas as pd

client = gwenlake.Client()

resp = client.prompts.list("gwenlake")
print(pd.DataFrame(resp))

prompt = client.prompts.get("gwenlake/rag")
print(prompt)

prompt = client.prompts.get("gwenlake/rag", input={"context": "test de contexte", "query": "ma question"})
print(prompt)
