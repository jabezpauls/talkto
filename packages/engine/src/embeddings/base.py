"""
Base embedding interface.
"""

from abc import ABC, abstractmethod
from typing import List
import numpy as np


class BaseEmbedding(ABC):
    """Base class for embedding providers"""

    # Embedding dimension
    dimension: int = 768

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Numpy array of shape (dimension,)
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            Numpy array of shape (n_texts, dimension)
        """
        pass

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embedding for a query.
        Override if query embeddings need special handling.

        Args:
            query: Query text to embed

        Returns:
            Numpy array of shape (dimension,)
        """
        return self.embed(query)
