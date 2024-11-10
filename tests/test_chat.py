import context
import gwenlake

client = gwenlake.Client()

# r = client.models.list()
# print(r)

messages = [
    {
        "role": "user",
        "content": "Describe Argentina in one sentence."
    }
]

# No streaming
response = client.chat.create(model="meta/llama-3.1-8b-instruct", messages=messages)
print("---", response["choices"][0]["message"]["content"])

# response = client.chat.create(model="llama-3.1-8b", messages=messages)
# print("---", response["choices"][0]["message"]["content"])

# response = client.chat.create(model="llama-3.1-8b", messages=messages, temperature=0.9)
# print("---", response["choices"][0]["message"]["content"])

# response = client.chat.create(model="llama-3.1-8b", messages=messages, temperature=0.9)
# print("---", response["choices"][0]["message"]["content"])


# Streaming
stream = client.chat.create(model="meta/llama-3.1-8b-instruct", messages=messages, stream=True)
for chunk in stream:
    print(chunk)
    # if chunk["choices"][0]["delta"]["content"]:
    #     print(chunk["choices"][0]["delta"]["content"], end="")
