import context
import pandas as pd
import gwenlake


list_of_texts = [
    "Olympic Games will be in Paris in 2024",
    "Do Not Watch This Movie! Not funny at all",
    "Can you help me write an email to my best friend?",
]

# embeddings
client = gwenlake.Client()
response = client.embeddings.create(input=list_of_texts, model="e5-base-v2")
for item in response.data:
    print(pd.DataFrame(item.embedding))

# langchain wrapper
from gwenlake.wrappers.langchain import GwenlakeEmbeddings
embeddings_model = GwenlakeEmbeddings()
embedded_query = embeddings_model.embed_query("What was the name mentioned in the conversation?")
print(embedded_query[:5])