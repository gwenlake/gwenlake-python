import context
import gwenlake

gwenlake.api_key = "test"

client = gwenlake.api.Client()
resp = client._post("test", {"text": "test de texte"})
print(resp)
