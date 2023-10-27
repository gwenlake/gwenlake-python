import os
import dotenv
import pandas as pd
import gwenlake
import sys 

os.chdir(os.path.dirname(os.path.abspath(__file__)))
dotenv.load_dotenv()

gwenlake.api_key = os.getenv("GWENLAKE_API_KEY")
data_id          = os.getenv("TEST_DATASET")

list_of_docs = [
    {
        "id": "test01",
        "title": "hello1",
        "description": "Do Not Watch This Movie!"
    },
    {
        "id": "test02",
        "title": "hello2",
        "description": "This movie is SOOOO funny!!! The acting is WONDERFUL."
    }
]

response = gwenlake.Client().upload_json(data_id=data_id, data=list_of_docs)
print(response)


