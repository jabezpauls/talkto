"""
Base loader interface for file loading.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


@dataclass
class LoadResult:
    """Result of loading a file"""
    content: str
    language: str
    metadata: dict

    @property
    def is_empty(self) -> bool:
        return len(self.content.strip()) == 0


class BaseLoader(ABC):
    """Base class for file loaders"""

    # File extensions this loader handles
    extensions: List[str] = []

    # Language identifier
    language: str = "text"

    @abstractmethod
    def load(self, file_path: Path) -> LoadResult:
        """
        Load content from a file.

        Args:
            file_path: Path to the file to load

        Returns:
            LoadResult containing the file content and metadata
        """
        pass

    def can_load(self, file_path: Path) -> bool:
        """Check if this loader can handle the given file"""
        suffix = file_path.suffix.lower()
        return suffix in self.extensions

    def get_metadata(self, file_path: Path) -> dict:
        """Get common metadata for a file"""
        return {
            "file": str(file_path),
            "language": self.language,
            "size": file_path.stat().st_size if file_path.exists() else 0
        }
