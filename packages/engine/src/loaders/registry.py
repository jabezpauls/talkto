"""
Loader registry for automatic file type detection.
"""

from pathlib import Path
from typing import Optional, List, Type

from .base import BaseLoader, LoadResult
from .text import TextLoader
from .code import CodeLoader
from .pdf import PDFLoader
from .docx import DocxLoader


class LoaderRegistry:
    """Registry of file loaders"""

    def __init__(self):
        self._loaders: List[BaseLoader] = []
        self._register_default_loaders()

    def _register_default_loaders(self):
        """Register built-in loaders"""
        self.register(TextLoader())
        self.register(CodeLoader())
        self.register(PDFLoader())
        self.register(DocxLoader())

    def register(self, loader: BaseLoader):
        """Register a loader"""
        self._loaders.append(loader)

    def get_loader(self, file_path: Path) -> Optional[BaseLoader]:
        """Get the appropriate loader for a file"""
        for loader in self._loaders:
            if loader.can_load(file_path):
                return loader
        return None

    def can_load(self, file_path: Path) -> bool:
        """Check if any loader can handle the file"""
        return self.get_loader(file_path) is not None

    def load(self, file_path: Path) -> Optional[LoadResult]:
        """Load a file using the appropriate loader"""
        loader = self.get_loader(file_path)
        if loader:
            return loader.load(file_path)
        return None

    @property
    def supported_extensions(self) -> List[str]:
        """Get all supported file extensions"""
        extensions = set()
        for loader in self._loaders:
            extensions.update(loader.extensions)
        return sorted(list(extensions))


# Global registry instance
_registry: Optional[LoaderRegistry] = None


def get_registry() -> LoaderRegistry:
    """Get the global loader registry"""
    global _registry
    if _registry is None:
        _registry = LoaderRegistry()
    return _registry


def get_loader(file_path: Path) -> Optional[BaseLoader]:
    """Get the appropriate loader for a file"""
    return get_registry().get_loader(file_path)
