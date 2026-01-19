"""
Retrieval module for RAG.
"""

import logging
from typing import List, Dict, Any

from ..vectorstore import FAISSStore
from ..embeddings.base import BaseEmbedding

logger = logging.getLogger(__name__)


class Retriever:
    """Retrieves relevant chunks for a query"""

    def __init__(
        self,
        vector_store: FAISSStore,
        embedding: BaseEmbedding,
        default_top_k: int = 5
    ):
        """
        Initialize retriever.

        Args:
            vector_store: FAISS vector store
            embedding: Embedding provider
            default_top_k: Default number of results
        """
        self.vector_store = vector_store
        self.embedding = embedding
        self.default_top_k = default_top_k

    def search(
        self,
        query: str,
        top_k: int = None,
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant chunks.

        Args:
            query: Search query
            top_k: Number of results (default: self.default_top_k)
            threshold: Minimum similarity threshold

        Returns:
            List of chunk dicts with score, file, content, etc.
        """
        if top_k is None:
            top_k = self.default_top_k

        # Generate query embedding
        query_embedding = self.embedding.embed_query(query)

        # Search vector store
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            threshold=threshold
        )

        logger.info(f"Retrieved {len(results)} chunks for query: {query[:50]}...")
        return results
