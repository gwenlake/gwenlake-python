from typing import Any, Dict, List, Optional

import requests
from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel, root_validator
from langchain.utils import get_from_dict_or_env


class GwenlakeEmbeddings(BaseModel, Embeddings):
    """Gwenlake embedding models."""

    session: Any  #: :meta private:
    model_name: str = "intfloat/e5-base-v2"
    gwenlake_api_key: Optional[str] = None
    endpoint_url: str = "https://api.gwenlake.com/v1/embeddings"


    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key exists in environment."""
        gwenlake_api_key = get_from_dict_or_env(values, "gwenlake_api_key", "GWENLAKE_API_KEY")
        values["gwenlake_api_key"] = gwenlake_api_key
        return values

    def _embed(self, input: List[str]) -> List[List[float]]:

        payload = {"input": input, "model": self.model_name}

        # HTTP headers for authorization
        headers = {
            "Authorization": f"Bearer {self.gwenlake_api_key}",
            "Content-Type": "application/json",
        }

        # send request
        try:
            response = requests.post(self.endpoint_url, headers=headers, json=payload)
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
                embeddings += self._embed(batch)
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
        return self._embed([text])[0]