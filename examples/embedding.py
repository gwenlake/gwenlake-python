import os
import dotenv
import pandas as pd
import gwenlake
import sys 

os.chdir(os.path.dirname(os.path.abspath(__file__)))
dotenv.load_dotenv()

list_of_texts = [
    "Do Not Watch This Movie!",
    "This movie is SOOOO funny!!! The acting is WONDERFUL.",
    "Everything about this movie is horrible, from the acting to the editing.",
]

client = gwenlake.Client()

response = client.embeddings.create(input=list_of_texts, model="e5-base-v2")
for item in response.data:
    print(pd.DataFrame(item.embedding))

