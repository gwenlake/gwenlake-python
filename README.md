# Gwenlake Python Library

The Gwenlake Python library provides convenient access to the Gwenlake API
from applications written in the Python language. It includes a
pre-defined set of classes for API resources that initialize
themselves dynamically from API responses which makes it compatible
with a wide range of versions of the Gwenlake API.


## Installation

If you just want to use the package, just run:

```sh
pip install -U git+https://github.com/gwenlake/gwenlake-python
```

## Usage

The library needs to be configured with your account's secret key. Either set it as the `GWENLAKE_API_KEY` environment variable before using the library:

```bash
export GWENLAKE_API_KEY='sk-...'
```

Or set `api_key` to its value with the Client:

```python
import gwenlake

client = gwenlake.client(api_key = "sk-...")
```
## Models

Use our inference platform to chat with models.

### List models
```python
r = client.models.list()
print(r)
```

### Chat
```python
messages = [
    {
        "role": "user",
        "content": "Anything about France?"
    }
]

r = client.chat.create(model="llama-3-8b", messages=messages)
print(r)
```

### Chat with streaming

The SDK also includes helpers to process streams and handle incoming events.

```python
stream = client.chat.stream(model="llama-3-8b", messages=messages)
for chunk in stream:
    if chunk["choices"][0]["delta"]["content"]:
        print(chunk["choices"][0]["delta"]["content"], end="")
```

## Embeddings

Use our inference platform for embeddings using [intfloat/e5-base-v2](https://huggingface.co/intfloat/e5-base-v2)
or the multilingual [intfloat/multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base) model (supports 100 languages).

```python
list_of_texts = [
    "Olympic Games will be in Paris in 2024",
    "Do Not Watch This Movie! Not funny at all",
    "Can you help me write an email to my best friend?",
]

response = client.embeddings.create(input=list_of_texts, model="e5-base-v2")
for item in response.data:
    print(item.embedding)
```

## Prompts

Discover and share prompts in the Gwenlake Hub.

### List prompts
```python
response = client.prompts.list()
print(response)
```

### Get a prompt
```python
prompt = client.prompts.get("gwenlake/rag")
print(prompt)

```


## Text Generation

Discover how to automatically combine prompts, datasets and models.

### Retrieval Augmented Generation (RAG)

```python
retriever = {
    "dataset": "gwenlake/csrd",
    "limit": 10
}

response = client.textgeneration.create(
    model="llama-3-8b",
    prompt="gwenlake/rag",
    input={"query": "Explain CSRD"},
    retriever=retriever)
print(response["output"][0]["text"])

```

## Files

Upload files on your private datasets.

```python
import gwenlake

client = gwenlake.Client()

# upload a file into a dataset
r = client.files.upload("myteam/mydataset", file="test.pdf")
print(r)

# upload a file in a subdir
r = client.files.upload("myteam/mydataset/docs", file="test.pdf")
print(r)

# list files
r = client.files.list("myteam/mydataset")
print(r)

r = client.files.list("myteam/mydataset/docs")
print(r)

# get file
file = client.files.get("myteam/mydataset/test.pdf")
```
