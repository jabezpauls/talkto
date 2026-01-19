"""
Base chunker interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any
import hashlib
import uuid


@dataclass
class ChunkerResult:
    """A chunk produced by a chunker"""
    id: str
    content: str
    metadata: Dict[str, Any]

    @staticmethod
    def generate_id(content: str, file: str, index: int) -> str:
        """Generate a unique chunk ID"""
        hash_input = f"{file}:{index}:{content[:100]}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


class BaseChunker(ABC):
    """Base class for chunkers"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Target size in tokens (approximate)
            chunk_overlap: Number of tokens to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @abstractmethod
    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[ChunkerResult]:
        """
        Split content into chunks.

        Args:
            content: The content to chunk
            metadata: Base metadata to include with each chunk

        Returns:
            List of ChunkerResult objects
        """
        pass

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Uses a rough approximation of 4 characters per token.
        """
        return len(text) // 4

    def content_hash(self, content: str) -> str:
        """Generate a content hash"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
