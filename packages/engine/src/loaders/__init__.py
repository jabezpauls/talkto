from .base import BaseLoader, LoadResult
from .text import TextLoader
from .code import CodeLoader
from .pdf import PDFLoader
from .docx import DocxLoader
from .registry import LoaderRegistry, get_loader, get_registry

__all__ = [
    'BaseLoader', 'LoadResult',
    'TextLoader', 'CodeLoader', 'PDFLoader', 'DocxLoader',
    'LoaderRegistry', 'get_loader', 'get_registry'
]
