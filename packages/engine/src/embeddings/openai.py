"""
OpenAI embedding provider.
"""

import os
import logging
from typing import List
import numpy as np

from .base import BaseEmbedding
from ..protocol.errors import EmbeddingError, ConfigurationError

logger = logging.getLogger(__name__)

# Model dimensions
MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbedding(BaseEmbedding):
    """OpenAI embedding provider"""

    def __init__(self, model: str = "text-embedding-3-small", api_key: str = None):
        super().__init__(model)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.dimension = MODEL_DIMENSIONS.get(model, 1536)
        self._client = None

        if not self.api_key:
            raise ConfigurationError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )

    @property
    def client(self):
        """Lazy-load OpenAI client"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise EmbeddingError(
                    "openai package not installed. Install with: pip install openai"
                )
        return self._client

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            embedding = response.data[0].embedding
            return np.array(embedding, dtype=np.float32)

        except Exception as e:
            raise EmbeddingError(f"Failed to generate embedding: {e}")

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        try:
            # OpenAI supports batch embedding
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )

            # Sort by index to ensure correct order
            embeddings = [None] * len(texts)
            for item in response.data:
                embeddings[item.index] = item.embedding

            return np.array(embeddings, dtype=np.float32)

        except Exception as e:
            raise EmbeddingError(f"Failed to generate batch embeddings: {e}")
