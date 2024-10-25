from typing import Any, Dict, List, Optional, cast
import requests
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from langchain.utils import convert_to_secret_str, get_from_dict_or_env


class GwenlakeEmbeddings(BaseModel, Embeddings):
    """Gwenlake embedding models."""

    model: str
    gwenlake_api_base: str = "https://api.gwenlake.com/v1/embeddings"
    gwenlake_api_key: Optional[SecretStr] = None
    
    model_config = ConfigDict(
        extra="forbid",
    )


    @model_validator(mode="before")
    @classmethod
    def validate_environment(cls, values: Dict) -> Dict:

        values["gwenlake_api_key"] = convert_to_secret_str(
            get_from_dict_or_env(values, "gwenlake_api_key", "GWENLAKE_API_KEY")
        )

        if "model" not in values:
            values["model"] = "e5-base-v2"

        return values

    def _embed(self, input: List[str]) -> List[List[float]]:

        api_key = cast(SecretStr, self.gwenlake_api_key).get_secret_value()

        payload = {"input": input, "model": self.model}

        # HTTP headers for authorization
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # send request
        try:
            response = requests.post(self.gwenlake_api_base, headers=headers, json=payload)
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Error raised by inference endpoint: {e}")
        
        if response.status_code != 200:
            raise ValueError(
                f"Error raised by inference API: rate limit exceeded.\nResponse: "
                f"{response.text}"
            )

        parsed_response = response.json()
        if "data" not in parsed_response:
            raise ValueError("Error raised by inference API.")

        embeddings = []
        for e in parsed_response["data"]:
            embeddings.append(e["embedding"])
        
        return embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Call out to Gwenlake's embedding endpoint.

        Args:
            texts: The list of texts to embed.

        Returns:
            List of embeddings, one for each text.
        """
        batch_size = 100
        embeddings = []
        try:
            for i in range(0, len(texts), batch_size):
                i_end = min(len(texts), i+batch_size)
                batch = texts[i:i_end]
                batch_processed = []
                for text in batch:
                    text = text.strip()
                    if not text.startswith("passage: "):
                        text = "passage: " + text
                    batch_processed.append(text)
                embeddings += self._embed(batch_processed)
        except:
            return None
        return embeddings


    def embed_query(self, text: str) -> List[float]:
        """Call out to Gwenlake's embedding endpoint.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.
        """
        text = text.strip()
        if not text.startswith("query: "):
            text = "query: " + text
        return self._embed([text])[0]