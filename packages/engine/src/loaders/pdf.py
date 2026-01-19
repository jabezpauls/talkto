"""
PDF file loader using pdfplumber.
"""

from pathlib import Path
from .base import BaseLoader, LoadResult


class PDFLoader(BaseLoader):
    """Loader for PDF files"""

    extensions = ['.pdf']
    language = "text"

    def load(self, file_path: Path) -> LoadResult:
        """Load text content from PDF"""
        try:
            import pdfplumber
        except ImportError:
            return LoadResult(
                content="",
                language="text",
                metadata={**self.get_metadata(file_path), "error": "pdfplumber not installed"}
            )

        try:
            pages_text = []

            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        pages_text.append(f"[Page {i + 1}]\n{text}")

            content = "\n\n".join(pages_text)

            metadata = self.get_metadata(file_path)
            metadata['pages'] = len(pages_text)

            return LoadResult(
                content=content,
                language="text",
                metadata=metadata
            )

        except Exception as e:
            return LoadResult(
                content="",
                language="text",
                metadata={**self.get_metadata(file_path), "error": str(e)}
            )
