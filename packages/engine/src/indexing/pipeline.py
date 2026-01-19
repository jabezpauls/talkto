"""
Full indexing pipeline for RAG.
"""

import os
import time
import hashlib
import logging
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..loaders import get_registry, LoadResult
from ..chunkers import RecursiveTextSplitter, CodeChunker
from ..embeddings import get_embedding_provider
from ..vectorstore import FAISSStore
from ..protocol.messages import IndexResult
from ..protocol.errors import IndexingError

logger = logging.getLogger(__name__)


class IndexingPipeline:
    """Full indexing pipeline: load -> chunk -> embed -> store"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize indexing pipeline.

        Args:
            config: Configuration dict
        """
        self.config = config
        self._loader_registry = get_registry()
        self._text_chunker = RecursiveTextSplitter()
        self._code_chunker = CodeChunker()
        self._embedding = None
        self._vector_store = None

    def _get_index_path(self, project_path: str) -> str:
        """Get the index path for a project"""
        from os.path import expanduser, join

        storage_path = expanduser("~/.talkto/indexes")

        # Use project path hash as index name
        path_hash = hashlib.sha256(project_path.encode()).hexdigest()[:16]

        return join(storage_path, path_hash)

    @property
    def embedding(self):
        """Lazy-load embedding provider"""
        if self._embedding is None:
            embedding_config = self.config.get("embedding", {})
            self._embedding = get_embedding_provider(embedding_config)
        return self._embedding

    def get_vector_store(self, project_path: str) -> FAISSStore:
        """Get or create vector store for a project"""
        index_path = self._get_index_path(project_path)
        return FAISSStore(
            index_path=index_path,
            dimension=self.embedding.dimension
        )

    def index(
        self,
        path: str,
        include: List[str] = None,
        exclude: List[str] = None,
        force: bool = False
    ) -> IndexResult:
        """
        Index files at the given path.

        Args:
            path: Path to file or directory
            include: Glob patterns to include
            exclude: Glob patterns to exclude
            force: Force re-index all files

        Returns:
            IndexResult with statistics
        """
        start_time = time.time()
        result = IndexResult()

        # Resolve path
        target_path = Path(path).resolve()
        if not target_path.exists():
            raise IndexingError(f"Path does not exist: {path}")

        # Get config
        index_config = self.config.get("index", {})
        include = include or index_config.get("include", ["**/*"])
        exclude = exclude or index_config.get("exclude", [])
        max_file_size = index_config.get("max_file_size", 5 * 1024 * 1024)

        # Get vector store
        vector_store = self.get_vector_store(str(target_path))

        # Collect files to index
        files_to_index = self._collect_files(
            target_path, include, exclude, max_file_size
        )

        logger.info(f"Found {len(files_to_index)} files to process")

        # Process files
        all_chunks = []
        all_embeddings = []

        for file_path in files_to_index:
            try:
                # Check if file needs reindexing
                content_hash = self._compute_file_hash(file_path)
                existing_hash = vector_store.get_file_hash(str(file_path))

                if not force and existing_hash == content_hash:
                    result.files_skipped += 1
                    continue

                # Delete old chunks if reindexing
                if existing_hash:
                    vector_store.delete_by_file(str(file_path))

                # Load file
                load_result = self._loader_registry.load(file_path)
                if not load_result or load_result.is_empty:
                    result.files_skipped += 1
                    continue

                # Chunk content
                chunks = self._chunk_content(load_result, file_path, target_path)
                if not chunks:
                    result.files_skipped += 1
                    continue

                # Generate embeddings
                chunk_texts = [c["content"] for c in chunks]
                embeddings = self.embedding.embed_batch(chunk_texts)

                all_chunks.extend(chunks)
                all_embeddings.extend(embeddings)

                # Track file
                vector_store.track_file(str(file_path), content_hash, len(chunks))
                result.files_processed += 1

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                result.errors.append({
                    "file": str(file_path),
                    "error": str(e)
                })

        # Add to vector store
        if all_chunks:
            import numpy as np
            embeddings_array = np.array(all_embeddings, dtype=np.float32)
            vector_store.add(embeddings_array, all_chunks)
            result.chunks_created = len(all_chunks)

        # Calculate duration
        result.duration = int((time.time() - start_time) * 1000)

        logger.info(
            f"Indexing complete: {result.files_processed} files, "
            f"{result.chunks_created} chunks, {result.duration}ms"
        )

        return result

    def _collect_files(
        self,
        root_path: Path,
        include: List[str],
        exclude: List[str],
        max_size: int
    ) -> List[Path]:
        """Collect files to index"""
        files = []

        # Handle single file
        if root_path.is_file():
            if self._should_index_file(root_path, include, exclude, max_size):
                return [root_path]
            return []

        # Handle directory
        for file_path in root_path.rglob("*"):
            if file_path.is_file():
                if self._should_index_file(file_path, include, exclude, max_size, root_path):
                    files.append(file_path)

        return files

    def _should_index_file(
        self,
        file_path: Path,
        include: List[str],
        exclude: List[str],
        max_size: int,
        root_path: Path = None
    ) -> bool:
        """Check if a file should be indexed"""
        # Check if loader exists
        if not self._loader_registry.can_load(file_path):
            return False

        # Check size
        try:
            if file_path.stat().st_size > max_size:
                return False
        except OSError:
            return False

        # Get relative path for pattern matching
        if root_path:
            rel_path = str(file_path.relative_to(root_path))
        else:
            rel_path = file_path.name

        # Check exclude patterns using Path.match (supports **)
        for pattern in exclude:
            if file_path.match(pattern):
                return False

        # Check include patterns
        # Default behavior: if no include patterns or ["**/*"], include all
        if not include or include == ["**/*"]:
            return True

        # Check if file matches any include pattern
        return any(file_path.match(pattern) for pattern in include)

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content"""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()[:16]
        except Exception:
            return ""

    def _chunk_content(
        self,
        load_result: LoadResult,
        file_path: Path,
        root_path: Path
    ) -> List[Dict[str, Any]]:
        """Chunk loaded content"""
        # Prepare metadata
        rel_path = str(file_path.relative_to(root_path)) if root_path in file_path.parents else str(file_path)
        metadata = {
            "file": rel_path,
            "language": load_result.language,
        }

        # Choose chunker based on content type
        if load_result.language in ['python', 'javascript', 'typescript']:
            chunker = self._code_chunker
        else:
            chunker = self._text_chunker

        # Chunk
        chunk_results = chunker.chunk(load_result.content, metadata)

        # Convert to dicts
        return [
            {
                "id": chunk.id,
                "content": chunk.content,
                "metadata": chunk.metadata
            }
            for chunk in chunk_results
        ]
