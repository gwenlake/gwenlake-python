from __future__ import annotations

from typing import TYPE_CHECKING

import json

from .resource import Resource


if TYPE_CHECKING:
    from .client import Client


__all__ = ["TextProcessing"]


class TextProcessing(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)


    def textreader(self, file: str):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        
        resp = self._client._request("POST", "/textprocessing/textreader", files={"file": open(file, "rb")})

        return resp.json()

    def vectorizer(self, file: str, chunk_size: int = 256, chunk_overlap: int = 50, meta: dict = {}, model="e5-base-v2"):
        if not isinstance(file, str):
            raise ValueError("file must be a string")
        
        url = f"/textprocessing/vectorizefile?chunk_size={chunk_size}&chunk_overlap={chunk_overlap}"
        if meta:
            url = url + "&meta=" + json.dumps(meta)

        resp = self._client._request("POST", url, files={"file": open(file, "rb")})

        obj = resp.json()

        if "data" in obj:
            chunks = [d["chunk"] for d in obj["data"]]
            embeddings = self._client.embeddings.create(input=chunks, model=model)
            for i, item in enumerate(embeddings.data):
                obj["data"][i]["embedding"] = item.embedding
    
        return obj
    