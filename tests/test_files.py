import context
import pandas as pd
import gwenlake



client = gwenlake.Client()

# resp = client.files.upload("taceconomics/alber", file=file)
# print(resp)

# resp = client.files.list("gwenlake/ai-education")
# print(pd.DataFrame(resp))

resp = client.files.list("gwenlake/test")
print(pd.DataFrame(resp))


file = "./docs/TAC ECONOMICS - Monthly Comments - Country Focus - October 2023.pdf"
resp = client.files.put(file=file)
# print(resp)

# file = "docs/TAC ECONOMICS - Monthly Comments - Country Focus - October 2023.pdf"
# resp = client.files.put(file=file, meta={"title": "test"}, "gwenlake/testup/test")
# print(resp)

# resp = client.files.list("gwenlake/testup")
# print(pd.DataFrame(resp))

# resp = client.files.list("gwenlake/testup/test")
# print(pd.DataFrame(resp))

# file = client.files.retrieve("gwenlake/ai-education/Generative_AI_in_Education__1702756729.pdf")
