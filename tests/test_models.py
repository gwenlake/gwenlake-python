import context
import gwenlake
import pandas as pd


client = gwenlake.Client()

resp = client.models.list()
print(pd.DataFrame(resp))


# input = "Olympic Games will be in Paris in 2024"
# response = client.models.run(model="gwenlake/e5-base-v2", input=input)
# print(response)

# input = "Olympic Games will be in Paris in 2024"
# stream = gwenlake.models.stream(model="llama-3.1-8b", input=input)
# print(reponse)

# for chunk in stream:
#     print(chunk)
    # print(chunk, end='', flush=True)
