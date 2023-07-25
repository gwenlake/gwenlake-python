import context
import pandas as pd
import gwenlake

client = gwenlake.api.Client()
resp = client.list_models()
print(pd.DataFrame(resp))
