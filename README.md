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

Or set `gwenlake.api_key` to its value:

```python
import gwenlake

gwenlake.api_key = "sk-..."
```

Or set `api_key` to its value with the Client:

```python
import gwenlake

client = gwenlake.client(api_key = "sk-...")
```


## Prompts

Discover and share prompts in the Gwenlake Hub.

```python
import gwenlake

client = gwenlake.Client()

response = client.prompts.list()
print(response)

# get a prompt in langchain format
prompt = client.prompts.get("gwenlake/rag")
print(prompt)

```

## Embeddings

Use our inference platform for embeddings using [intfloat/e5-base-v2](https://huggingface.co/intfloat/e5-base-v2)
or the multilingual [intfloat/multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base) model (supports 100 languages).

```python
import pandas as pd
import gwenlake

list_of_texts = [
    "Olympic Games will be in Paris in 2024",
    "Do Not Watch This Movie! Not funny at all",
    "Can you help me write an email to my best friend?",
]

client = gwenlake.Client()

response = client.embeddings.create(input=list_of_texts, model="e5-base-v2")
for item in response.data:
    print(pd.DataFrame(item.embedding))
```

## Models

Use our inference platform to run public or private models from the hub.

```python
import gwenlake

client = gwenlake.Client()

r = client.models.list()
print(r)

r = client.models.create(
    input="Olympic Games will be in Paris in 2024",
    model="e5-base-v2",
    )
print(r)
```

## Chat

Use our inference platform to chat.

```python
import gwenlake

client = gwenlake.Client()

messages = [
    {
        "role": "user",
        "content": "Anything about France?"
    }
]

# No streaming
r = client.chat.create(model="gpt-35-turbo-16k", messages=messages)
print(r)

# Streaming
stream = client.chat.stream(model="gpt-35-turbo-16k", messages=messages)
for chunk in stream:
    if chunk["choices"][0]["delta"]["content"]:
        print(chunk["choices"][0]["delta"]["content"], end="")
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

## Chat with RAG (Automated Retrieval Augmented Generation)

Use our inference platform to chat on your documents.

```python
import gwenlake

client = gwenlake.Client()

messages = [
    {
        "role": "user",
        "content": "Anything about France?"
    }
]

r = client.chat.create(model="gpt-35-turbo-16k", messages=messages, data="myteam/documents")
print(r)

```