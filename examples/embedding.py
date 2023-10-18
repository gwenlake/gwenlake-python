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

gwenlake.api_key = os.getenv("GWENLAKE_API_KEY")
embeddings = gwenlake.get_embeddings(list_of_texts)
print(pd.DataFrame(embeddings))


