import context
import gwenlake

client = gwenlake.Client()

retriever = {
    "dataset": "gwenlake/csrd",
    "limit": 10
}

response = client.textgeneration.create(model="llama-3-8b", prompt="gwenlake/rag", input={"query": "Explain CSRD"}, retriever=retriever)
print(response["output"][0]["text"])