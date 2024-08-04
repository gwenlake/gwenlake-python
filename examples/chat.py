import gwenlake

client = gwenlake.Client(api_key="xxx")

# list models
r = client.models.list()
print(r)

# run model (no streaming)
messages = [
    {
        "role": "user",
        "content": "Describe Argentina in one sentence"
    }
]

response = client.chat.create(model="llama-3.1-8b", messages=messages)
print(response)

response = client.chat.create(model="llama-3.1-8b", messages=messages, temperature=0.9)
print(response)

# Streaming
stream = client.chat.stream(model="llama-3-8b", messages=messages)
for chunk in stream:
    if chunk["choices"][0]["delta"]["content"]:
        print(chunk["choices"][0]["delta"]["content"], end="")
