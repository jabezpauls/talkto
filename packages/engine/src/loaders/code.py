"""
Code file loader for programming language files.
"""

from pathlib import Path
from .base import BaseLoader, LoadResult


# Extension to language mapping
EXTENSION_LANGUAGE_MAP = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.jsx': 'javascript',
    '.tsx': 'typescript',
    '.java': 'java',
    '.c': 'c',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.h': 'c',
    '.hpp': 'cpp',
    '.cs': 'csharp',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.php': 'php',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.scala': 'scala',
    '.sh': 'bash',
    '.bash': 'bash',
    '.zsh': 'zsh',
    '.sql': 'sql',
    '.r': 'r',
    '.R': 'r',
    '.lua': 'lua',
    '.pl': 'perl',
    '.pm': 'perl',
    '.yml': 'yaml',
    '.yaml': 'yaml',
    '.json': 'json',
    '.xml': 'xml',
    '.html': 'html',
    '.htm': 'html',
    '.css': 'css',
    '.scss': 'scss',
    '.sass': 'sass',
    '.less': 'less',
    '.vue': 'vue',
    '.svelte': 'svelte',
}


class CodeLoader(BaseLoader):
    """Loader for code files"""

    extensions = list(EXTENSION_LANGUAGE_MAP.keys())
    language = "code"

    def load(self, file_path: Path) -> LoadResult:
        """Load code content from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
            except Exception:
                content = ""

        # Determine language from extension
        suffix = file_path.suffix.lower()
        lang = EXTENSION_LANGUAGE_MAP.get(suffix, 'text')

        metadata = self.get_metadata(file_path)
        metadata['language'] = lang

        return LoadResult(
            content=content,
            language=lang,
            metadata=metadata
        )
