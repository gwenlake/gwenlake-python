# from langchain.pydantic_v1 import BaseModel, Extra
from typing import (
    Any,
    List,
    Optional,
    cast
)

# from langchain.embeddings.base import Embeddings
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.callbacks.manager import CallbackManagerForRetrieverRun
from langchain.schema import Document
from typing import List, Dict, Any

import logging

logger = logging.getLogger(__name__)


class SelfQueryRetrieverWithScores(SelfQueryRetriever):
    
    def _get_docs_with_query(
        self, query: str, search_kwargs: Dict[str, Any]
    ) -> List[Document]:
        docs = self.vectorstore.similarity_search_with_score(query, **search_kwargs)
        return docs
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Get documents relevant for a query.

        Args:
            query: string to find relevant documents for

        Returns:
            List of relevant documents
        """
        structured_query = self.query_constructor.invoke(
            {"query": query}, config={"callbacks": run_manager.get_child()}
        )
        self.verbose = True
        if self.verbose:
            print(f"Generated Query: {structured_query}")
            logger.info(f"Generated Query: {structured_query}")
        
        new_query, search_kwargs = self._prepare_query(query, structured_query)
        new_query = new_query.strip()
        if not new_query and not structured_query.filter:
            return []

        docs_and_scores = self._get_docs_with_query(new_query, search_kwargs)
        # print(docs_and_scores)
        for doc, score in docs_and_scores:
            doc.metadata = {**doc.metadata, **{"score": score}}
        return [doc for (doc, _) in docs_and_scores]


# class GwenlakeEmbedding(BaseModel, Embeddings):
#     def __init__(self, **kwargs: Any):
#         """Initialize the sentence_transformer."""
#         super().__init__(**kwargs)

#     class Config:
#         """Configuration for this pydantic object."""
#         extra = Extra.forbid

   
#     def embed_documents(self, texts: List[str], chunk_size: Optional[int] = 0) -> List[List[float]]:
#         res = gwenlake.get_embeddings(texts)
#         print(res)
#         return  res

#     async def aembed_documents(self, texts: List[str], chunk_size: Optional[int] = 0) -> List[List[float]]:
#        return await  gwenlake.get_embeddings(texts)

#     def embed_query(self, text: str) -> List[float]:
#         return gwenlake.get_embeddings([text])[0]

#     async def aembed_query(self, text: str) -> List[float]:
#         return  gwenlake.get_embeddings([text])[0]