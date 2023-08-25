import os
import dotenv
import pandas as pd
import gwenlake

os.chdir(os.path.dirname(os.path.abspath(__file__)))
dotenv.load_dotenv()

documents = [
    "My name is Sylvain",
    "My name is not Sylvain",
]

embeddings = gwenlake.api.APIClient().embed_documents(documents)
print(pd.DataFrame(embeddings))
