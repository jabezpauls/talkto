"""
Text file loader for markdown, plain text, and similar formats.
"""

from pathlib import Path
from .base import BaseLoader, LoadResult


class TextLoader(BaseLoader):
    """Loader for text-based files"""

    extensions = ['.md', '.txt', '.rst', '.text', '.markdown']
    language = "text"

    def load(self, file_path: Path) -> LoadResult:
        """Load text content from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encodings
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
            except Exception:
                content = ""

        # Determine language based on extension
        suffix = file_path.suffix.lower()
        if suffix == '.md' or suffix == '.markdown':
            lang = 'markdown'
        elif suffix == '.rst':
            lang = 'restructuredtext'
        else:
            lang = 'text'

        return LoadResult(
            content=content,
            language=lang,
            metadata=self.get_metadata(file_path)
        )
