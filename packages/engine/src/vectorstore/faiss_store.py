"""
FAISS vector store with SQLite metadata.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from .metadata import MetadataStore

logger = logging.getLogger(__name__)


class FAISSStore:
    """FAISS index with SQLite metadata storage"""

    def __init__(self, index_path: str, dimension: int = 768):
        """
        Initialize FAISS store.

        Args:
            index_path: Path to index directory
            dimension: Embedding dimension (768 for nomic-embed-text)
        """
        self.index_path = Path(index_path)
        self.dimension = dimension
        self.index_file = self.index_path / "vectors.faiss"
        self.metadata_file = self.index_path / "meta.db"

        # Create directory if needed
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Initialize FAISS
        self._index = None
        self._faiss = None

        # Initialize metadata store
        self.metadata = MetadataStore(str(self.metadata_file))

    @property
    def faiss(self):
        """Lazy-load FAISS"""
        if self._faiss is None:
            try:
                import faiss
                self._faiss = faiss
            except ImportError:
                raise ImportError("faiss-cpu is required. Install with: pip install faiss-cpu")
        return self._faiss

    @property
    def index(self):
        """Get or create FAISS index"""
        if self._index is None:
            if self.index_file.exists():
                self._index = self.faiss.read_index(str(self.index_file))
                logger.info(f"Loaded FAISS index with {self._index.ntotal} vectors")
            else:
                # Use IndexFlatIP for cosine similarity (after normalization)
                self._index = self.faiss.IndexFlatIP(self.dimension)
                logger.info(f"Created new FAISS index (dim={self.dimension})")
        return self._index

    def add(self, embeddings: np.ndarray, chunks: List[Dict[str, Any]]) -> int:
        """
        Add embeddings and metadata to the store.

        Args:
            embeddings: Numpy array of embeddings (n, dimension)
            chunks: List of chunk dicts with id, content, metadata

        Returns:
            Number of vectors added
        """
        if len(embeddings) != len(chunks):
            raise ValueError("Embeddings and chunks must have same length")

        if len(embeddings) == 0:
            return 0

        # Ensure correct dtype and shape
        embeddings = np.asarray(embeddings, dtype=np.float32)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        # Normalize for cosine similarity
        self.faiss.normalize_L2(embeddings)

        # Get starting ID
        start_id = self.index.ntotal

        # Add to FAISS
        self.index.add(embeddings)

        # Add metadata
        batch_data = []
        for i, chunk in enumerate(chunks):
            vector_id = start_id + i
            batch_data.append((vector_id, chunk))

        self.metadata.add_batch(batch_data)

        # Save index
        self.save()

        logger.info(f"Added {len(chunks)} vectors to index (total: {self.index.ntotal})")
        return len(chunks)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.

        Args:
            query_embedding: Query vector
            top_k: Number of results
            threshold: Minimum similarity threshold

        Returns:
            List of dicts with score, file, content, etc.
        """
        if self.index.ntotal == 0:
            return []

        # Prepare query
        query = np.asarray(query_embedding, dtype=np.float32)
        if query.ndim == 1:
            query = query.reshape(1, -1)

        # Normalize query for cosine similarity
        self.faiss.normalize_L2(query)

        # Search
        scores, ids = self.index.search(query, min(top_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1 or score < threshold:
                continue

            metadata = self.metadata.get(int(idx))
            if metadata:
                results.append({
                    "score": float(score),
                    **metadata
                })

        return results

    def delete_by_file(self, file_path: str) -> int:
        """
        Delete all chunks from a specific file.
        Note: FAISS doesn't support efficient deletion,
        so we mark as deleted in metadata.

        Args:
            file_path: Path to file

        Returns:
            Number of chunks deleted
        """
        return self.metadata.delete_by_file(file_path)

    def get_indexed_files(self) -> List[Dict[str, Any]]:
        """Get list of all indexed files with their hashes"""
        return self.metadata.get_indexed_files()

    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Get content hash for a file"""
        return self.metadata.get_file_hash(file_path)

    def track_file(self, file_path: str, content_hash: str, chunk_count: int) -> None:
        """Track an indexed file"""
        self.metadata.track_file(file_path, content_hash, chunk_count)

    def save(self):
        """Save index to disk"""
        self.faiss.write_index(self.index, str(self.index_file))
        logger.debug("FAISS index saved")

    def clear(self):
        """Clear all data"""
        self._index = self.faiss.IndexFlatIP(self.dimension)
        self.metadata.clear()
        self.save()
        logger.info("Index cleared")

    @property
    def total_vectors(self) -> int:
        """Get total number of vectors"""
        return self.index.ntotal

    def close(self):
        """Close resources"""
        self.metadata.close()
