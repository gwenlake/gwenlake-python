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


## Hub

Discover and share prompts in the Gwenlake Hub.

```python
import gwenlake

gwenlake.api_key = "sk-..."

# get a prompt from the hub
prompt_template = gwenlake.hub.pull("/prompts/gwenlake/rag")

# format the prompt using variables
prompt = prompt_template.format(
    context="Olympic Games will be in Paris in 2024",
    question="Where will be the next OlympicG?")

# Send to ChatGPT and get answer
llm = gwenlake.chat.ChatOpenAI()
response = llm.chat(prompt)

>> The next Olympic Games will be in Paris in 2024.

```


## Embeddings

Use our inference platform for embeddings using [intfloat/e5-base-v2](https://huggingface.co/intfloat/e5-base-v2) or the multilingual [intfloat/multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base) model (supports 100 languages).

```python
import pandas as pd
import gwenlake
from gwenlake.embeddings.langchain import GwenlakeEmbeddings

gwenlake.api_key = "sk-..."

list_of_texts = [
    "Olympic Games will be in Paris in 2024",
    "Do Not Watch This Movie! Not funny at all",
    "Can you help me write an email to my best friend?",
]


# default e5-base-v2 model
embeddings = GwenlakeEmbeddings()

query_result = embeddings.embed_query(list_of_texts[0])
print(query_result[:5])


# multilingual-e5-base model
embeddings = GwenlakeEmbeddings(model_name="multilingual-e5-base")

query_result = embeddings.embed_documents(list_of_texts)
print(pd.DataFrame(query_result))
```


## Text Processing

Use our inference platform for automated text processing (pdf to text, text to chunks and embeddings).

```python
import gwenlake

gwenlake.api_key = "sk-..."

# Simple PDF to Text reader
r = gwenlake.Client().textreader(file="file.pdf")
print(r)

# Advanced vectorizer (PDF -> text -> chunks -> embeddings)
r = gwenlake.Client().vectorize_file(file="file.pdf", chunk_size=500, chunk_overlap=100)
print(r)

```