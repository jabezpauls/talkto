"""
Code chunker using tree-sitter for language-aware splitting.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from .base import BaseChunker, ChunkerResult
from .text import RecursiveTextSplitter

logger = logging.getLogger(__name__)

# Language to tree-sitter parser mapping
LANGUAGE_PARSERS = {
    'python': 'tree_sitter_python',
    'javascript': 'tree_sitter_javascript',
    'typescript': 'tree_sitter_javascript',  # Uses same grammar
}

# Node types that represent complete units (functions, classes, etc.)
FUNCTION_NODE_TYPES = {
    'python': ['function_definition', 'class_definition', 'decorated_definition'],
    'javascript': ['function_declaration', 'function_expression', 'arrow_function',
                   'class_declaration', 'method_definition'],
    'typescript': ['function_declaration', 'function_expression', 'arrow_function',
                   'class_declaration', 'method_definition'],
}


class CodeChunker(BaseChunker):
    """
    Chunk code files using tree-sitter for syntax-aware splitting.
    Falls back to text splitting if tree-sitter is unavailable.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        super().__init__(chunk_size, chunk_overlap)
        self._parsers: Dict[str, Any] = {}
        self._fallback = RecursiveTextSplitter(chunk_size, chunk_overlap)
        self._tree_sitter_available = self._check_tree_sitter()

    def _check_tree_sitter(self) -> bool:
        """Check if tree-sitter is available"""
        try:
            import tree_sitter
            return True
        except ImportError:
            logger.warning("tree-sitter not available, using fallback text splitting")
            return False

    def _get_parser(self, language: str) -> Optional[Any]:
        """Get or create a tree-sitter parser for a language"""
        if not self._tree_sitter_available:
            return None

        if language in self._parsers:
            return self._parsers[language]

        parser_module = LANGUAGE_PARSERS.get(language)
        if not parser_module:
            return None

        try:
            import tree_sitter
            import importlib

            # Import the language module
            lang_module = importlib.import_module(parser_module)
            lang = tree_sitter.Language(lang_module.language())

            parser = tree_sitter.Parser(lang)
            self._parsers[language] = parser
            return parser

        except Exception as e:
            logger.warning(f"Failed to create parser for {language}: {e}")
            return None

    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[ChunkerResult]:
        """Chunk code content"""
        language = metadata.get("language", "text")

        # Try tree-sitter parsing
        parser = self._get_parser(language)
        if parser:
            try:
                return self._chunk_with_tree_sitter(content, metadata, parser, language)
            except Exception as e:
                logger.warning(f"Tree-sitter parsing failed: {e}, using fallback")

        # Fallback to text splitting
        return self._fallback.chunk(content, metadata)

    def _chunk_with_tree_sitter(
        self,
        content: str,
        metadata: Dict[str, Any],
        parser: Any,
        language: str
    ) -> List[ChunkerResult]:
        """Chunk code using tree-sitter"""
        tree = parser.parse(bytes(content, 'utf8'))
        root = tree.root_node

        # Extract function/class definitions
        chunks = []
        function_types = FUNCTION_NODE_TYPES.get(language, [])

        # First pass: collect all significant nodes
        nodes_to_chunk = []
        self._collect_nodes(root, function_types, nodes_to_chunk)

        if not nodes_to_chunk:
            # No significant nodes found, fall back to text splitting
            return self._fallback.chunk(content, metadata)

        # Process each significant node
        for i, node in enumerate(nodes_to_chunk):
            node_text = content[node.start_byte:node.end_byte]
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            # Determine chunk type
            chunk_type = self._get_chunk_type(node.type, language)

            # If chunk is too large, split it further
            if self.estimate_tokens(node_text) > self.chunk_size:
                sub_chunks = self._split_large_node(node_text, metadata, start_line, chunk_type)
                chunks.extend(sub_chunks)
            else:
                chunk_id = ChunkerResult.generate_id(node_text, metadata.get("file", ""), i)
                chunks.append(ChunkerResult(
                    id=chunk_id,
                    content=node_text,
                    metadata={
                        **metadata,
                        "chunk_index": i,
                        "chunk_type": chunk_type,
                        "lines": f"{start_line}-{end_line}",
                        "content_hash": self.content_hash(node_text)
                    }
                ))

        return chunks

    def _collect_nodes(self, node: Any, target_types: List[str], result: List[Any]):
        """Recursively collect significant nodes"""
        if node.type in target_types:
            result.append(node)
        else:
            for child in node.children:
                self._collect_nodes(child, target_types, result)

    def _get_chunk_type(self, node_type: str, language: str) -> str:
        """Map tree-sitter node type to chunk type"""
        if 'class' in node_type:
            return 'class'
        elif 'function' in node_type or 'method' in node_type or 'arrow' in node_type:
            return 'function'
        elif 'decorated' in node_type:
            return 'function'  # Usually decorated functions
        return 'code'

    def _split_large_node(
        self,
        content: str,
        metadata: Dict[str, Any],
        start_line: int,
        chunk_type: str
    ) -> List[ChunkerResult]:
        """Split a large code block into smaller chunks"""
        # Use the text splitter but preserve code context
        lines = content.split('\n')
        chunks = []

        current_chunk = []
        current_tokens = 0
        chunk_start_line = start_line

        for i, line in enumerate(lines):
            line_tokens = self.estimate_tokens(line)

            if current_tokens + line_tokens > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = '\n'.join(current_chunk)
                chunk_id = ChunkerResult.generate_id(chunk_text, metadata.get("file", ""), len(chunks))

                chunks.append(ChunkerResult(
                    id=chunk_id,
                    content=chunk_text,
                    metadata={
                        **metadata,
                        "chunk_index": len(chunks),
                        "chunk_type": chunk_type,
                        "lines": f"{chunk_start_line}-{chunk_start_line + len(current_chunk) - 1}",
                        "content_hash": self.content_hash(chunk_text)
                    }
                ))

                # Start new chunk with overlap
                overlap_lines = min(5, len(current_chunk))
                current_chunk = current_chunk[-overlap_lines:] + [line]
                chunk_start_line = start_line + i - overlap_lines + 1
                current_tokens = self.estimate_tokens('\n'.join(current_chunk))
            else:
                current_chunk.append(line)
                current_tokens += line_tokens

        # Save final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunk_id = ChunkerResult.generate_id(chunk_text, metadata.get("file", ""), len(chunks))

            chunks.append(ChunkerResult(
                id=chunk_id,
                content=chunk_text,
                metadata={
                    **metadata,
                    "chunk_index": len(chunks),
                    "chunk_type": chunk_type,
                    "lines": f"{chunk_start_line}-{chunk_start_line + len(current_chunk) - 1}",
                    "content_hash": self.content_hash(chunk_text)
                }
            ))

        return chunks
