"""
Recursive text splitter with token awareness.
"""

from typing import List, Dict, Any

from .base import BaseChunker, ChunkerResult


class RecursiveTextSplitter(BaseChunker):
    """Split text into chunks while preserving semantic boundaries"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: List[str] = None
    ):
        super().__init__(chunk_size, chunk_overlap)
        self.separators = separators or [
            "\n\n",      # Paragraph
            "\n",        # Line
            ". ",        # Sentence
            ", ",        # Clause
            " ",         # Word
            ""           # Character
        ]

    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[ChunkerResult]:
        """Split text into chunks"""
        chunks = self._split_text(content, self.separators)

        results = []
        for i, chunk_text in enumerate(chunks):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue

            chunk_id = ChunkerResult.generate_id(chunk_text, metadata.get("file", ""), i)

            results.append(ChunkerResult(
                id=chunk_id,
                content=chunk_text,
                metadata={
                    **metadata,
                    "chunk_index": i,
                    "chunk_type": "text",
                    "content_hash": self.content_hash(chunk_text)
                }
            ))

        return results

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text using separators"""
        if not text:
            return []

        # Check if text fits in one chunk
        if self.estimate_tokens(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        # Try each separator
        for sep in separators:
            if sep and sep in text:
                splits = text.split(sep)
                chunks = []
                current_chunk = []
                current_tokens = 0

                for split in splits:
                    split_tokens = self.estimate_tokens(split)

                    if current_tokens + split_tokens > self.chunk_size and current_chunk:
                        # Save current chunk
                        chunk_text = sep.join(current_chunk)
                        chunks.append(chunk_text.strip())

                        # Start new chunk with overlap
                        overlap_parts = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk[-1:]
                        overlap_text = sep.join(overlap_parts)

                        if self.estimate_tokens(overlap_text) < self.chunk_overlap * 2:
                            current_chunk = [overlap_text, split] if overlap_text else [split]
                        else:
                            current_chunk = [split]

                        current_tokens = self.estimate_tokens(sep.join(current_chunk))
                    else:
                        current_chunk.append(split)
                        current_tokens += split_tokens

                if current_chunk:
                    chunks.append(sep.join(current_chunk).strip())

                # Recursively split any chunks still too large
                final_chunks = []
                for chunk in chunks:
                    if self.estimate_tokens(chunk) > self.chunk_size:
                        # Use next separator
                        remaining_seps = separators[separators.index(sep) + 1:]
                        final_chunks.extend(self._split_text(chunk, remaining_seps))
                    else:
                        if chunk.strip():
                            final_chunks.append(chunk.strip())

                return final_chunks

        # No separator found, force split by size
        return self._force_split(text)

    def _force_split(self, text: str) -> List[str]:
        """Force split by character count when no separator works"""
        chars_per_chunk = self.chunk_size * 4  # Convert tokens to chars
        overlap_chars = self.chunk_overlap * 4
        chunks = []

        start = 0
        while start < len(text):
            end = min(start + chars_per_chunk, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move forward accounting for overlap
            start = end - overlap_chars
            if start >= len(text) - overlap_chars:
                break

        return chunks
