from importlib import metadata

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available.
    __version__ = ""


from gwenlake.client import Client

__all__ = [
    "__version__",
    "Client",
]

api_key: str | None = None

base_url: str | None = None


default_client = Client()

chat = default_client.chat
embeddings = default_client.embeddings
files = default_client.files
datasets = default_client.datasets
textgeneration = default_client.textgeneration
models = default_client.models
prompts = default_client.prompts
reader = default_client.reader
