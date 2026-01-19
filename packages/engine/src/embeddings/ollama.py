"""
Ollama embedding provider.
"""

import logging
from typing import List
import numpy as np

from .base import BaseEmbedding
from ..protocol.errors import OllamaNotRunningError, ModelNotFoundError, EmbeddingError

logger = logging.getLogger(__name__)

# Model dimensions
MODEL_DIMENSIONS = {
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "all-minilm": 384,
}


class OllamaEmbedding(BaseEmbedding):
    """Ollama embedding provider using local models"""

    def __init__(self, model: str = "nomic-embed-text", base_url: str = None):
        super().__init__(model)
        self.base_url = base_url or "http://localhost:11434"
        self.dimension = MODEL_DIMENSIONS.get(model, 768)
        self._client = None

    @property
    def client(self):
        """Lazy-load Ollama client"""
        if self._client is None:
            try:
                import ollama
                self._client = ollama.Client(host=self.base_url)
            except ImportError:
                raise EmbeddingError("ollama package not installed")
        return self._client

    def _check_connection(self):
        """Check if Ollama is running"""
        try:
            self.client.list()
        except Exception as e:
            if "Connection refused" in str(e) or "connection" in str(e).lower():
                raise OllamaNotRunningError()
            raise EmbeddingError(f"Failed to connect to Ollama: {e}")

    def _ensure_model(self):
        """Ensure the model is available"""
        try:
            models = self.client.list()
            model_names = [m.model for m in models.models]

            # Check if model exists (with or without tag)
            model_base = self.model.split(':')[0]
            if not any(model_base in name for name in model_names):
                logger.info(f"Model {self.model} not found, pulling...")
                self.client.pull(self.model)

        except Exception as e:
            if "not found" in str(e).lower():
                raise ModelNotFoundError(self.model)
            raise

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        self._check_connection()
        self._ensure_model()

        try:
            response = self.client.embed(
                model=self.model,
                input=text
            )
            embedding = response.embeddings[0]
            return np.array(embedding, dtype=np.float32)

        except Exception as e:
            raise EmbeddingError(f"Failed to generate embedding: {e}")

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        self._check_connection()
        self._ensure_model()

        try:
            # Ollama supports batch embedding
            response = self.client.embed(
                model=self.model,
                input=texts
            )
            embeddings = response.embeddings
            return np.array(embeddings, dtype=np.float32)

        except Exception as e:
            # Fall back to individual embeddings if batch fails
            logger.warning(f"Batch embedding failed, falling back to individual: {e}")
            embeddings = []
            for text in texts:
                emb = self.embed(text)
                embeddings.append(emb)
            return np.array(embeddings, dtype=np.float32)
