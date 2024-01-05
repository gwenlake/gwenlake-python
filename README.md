# Gwenlake Python Library

The Gwenlake Python library provides convenient access to the Gwenlake API
from applications written in the Python language. It includes a
pre-defined set of classes for API resources that initialize
themselves dynamically from API responses which makes it compatible
with a wide range of versions of the Gwenlake API.


## Installation

You don't need this source code unless you want to modify the package. If you just
want to use the package, just run:

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


## Hub

Discover and share in the Gwenlake Hub.

```python
import gwenlake

client = gwenlake.Client()

response = client.hub.list()
print(response)
```


## Embeddings

Use our inference platform for embeddings using [intfloat/e5-base-v2](https://huggingface.co/intfloat/e5-base-v2) or the multilingual [intfloat/multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base) model (supports 100 languages).

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


## Text Processing

Use our inference platform for automated text processing (pdf to text, text to chunks and embeddings).

```python
import gwenlake

client = gwenlake.Client()

# PDF to Text reader
r = client.textprocessing.textreader(file="file.pdf")
print(pd.DataFrame(r["data"]))

# Vectorizer (PDF -> text -> chunks -> embeddings)
r = client.textprocessing.vectorizer(file="file.pdf")
print(pd.DataFrame(r["data"]))

```


## Run models

Use our inference platform to run models available on the hub.

```python
import gwenlake

client = gwenlake.Client()

r = client.models.list()
print(r)

r = client.models.run(input="Olympic Games will be in Paris in 2024", model="gwenlake/e5-base-v2")
print(r)
```