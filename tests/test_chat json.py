import context
import gwenlake

client = gwenlake.Client()

messages = [
    {
        "role": "user",
        "content": "Describe Argentina in one sentence. Only respond with valid JSON."
    }
]

# No JSON
response = client.chat.create(model="meta/llama-3.1-8b-instruct", messages=messages)
print(response["choices"][0]["message"]["content"])

# JSON
# You are a helpful assistant that answers in JSON. Here's the json schema you must adhere to:\n<schema>\n{pydantic_schema}\n</schema>
# response = client.chat.create(model="meta/llama-3.1-8b-instruct", messages=messages, response_format={ "type": "json_object" })
# print(response["choices"][0]["message"]["content"])
