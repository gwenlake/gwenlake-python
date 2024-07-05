import gwenlake

client = gwenlake.Client(api_key="sk_XXX")

# list models
r = client.models.list()
print(r)

# run model (no streaming)
messages = [
    {
        "role": "user",
        "content": "Anything on Argentina?"
    }
]

response = client.chat.create(model="llama-3-8b", messages=messages)
print(response)


# Streaming
stream = client.chat.stream(model="llama-3-8b", messages=messages)
for chunk in stream:
    if chunk["choices"][0]["delta"]["content"]:
        print(chunk["choices"][0]["delta"]["content"], end="")
