"""
SQLite metadata store for chunk information.
"""

import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MetadataStore:
    """SQLite-based metadata storage for chunks"""

    def __init__(self, db_path: str):
        """
        Initialize metadata store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection = None
        self._init_db()

    @property
    def connection(self) -> sqlite3.Connection:
        """Get database connection"""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def _init_db(self):
        """Initialize database schema"""
        cursor = self.connection.cursor()

        # Chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                chunk_id TEXT UNIQUE,
                file TEXT NOT NULL,
                lines TEXT,
                language TEXT,
                chunk_type TEXT,
                content_hash TEXT,
                content TEXT,
                indexed_at TEXT,
                deleted INTEGER DEFAULT 0
            )
        """)

        # Files table for tracking indexed files
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE,
                content_hash TEXT,
                indexed_at TEXT,
                chunk_count INTEGER DEFAULT 0
            )
        """)

        # Indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(content_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path)")

        self.connection.commit()

    def add(self, vector_id: int, chunk: Dict[str, Any]) -> None:
        """
        Add metadata for a chunk.

        Args:
            vector_id: The FAISS vector ID
            chunk: Chunk data containing id, content, and metadata
        """
        metadata = chunk.get("metadata", {})

        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO chunks
            (id, chunk_id, file, lines, language, chunk_type, content_hash, content, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vector_id,
            chunk.get("id", ""),
            metadata.get("file", ""),
            metadata.get("lines"),
            metadata.get("language", "text"),
            metadata.get("chunk_type", "text"),
            metadata.get("content_hash", ""),
            chunk.get("content", ""),
            metadata.get("indexed_at", "")
        ))
        self.connection.commit()

    def add_batch(self, chunks: List[tuple]) -> None:
        """
        Add metadata for multiple chunks.

        Args:
            chunks: List of (vector_id, chunk_dict) tuples
        """
        cursor = self.connection.cursor()

        for vector_id, chunk in chunks:
            metadata = chunk.get("metadata", {})
            cursor.execute("""
                INSERT OR REPLACE INTO chunks
                (id, chunk_id, file, lines, language, chunk_type, content_hash, content, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                vector_id,
                chunk.get("id", ""),
                metadata.get("file", ""),
                metadata.get("lines"),
                metadata.get("language", "text"),
                metadata.get("chunk_type", "text"),
                metadata.get("content_hash", ""),
                chunk.get("content", ""),
                metadata.get("indexed_at", "")
            ))

        self.connection.commit()

    def get(self, vector_id: int) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a vector ID.

        Args:
            vector_id: The FAISS vector ID

        Returns:
            Chunk metadata dict or None
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM chunks WHERE id = ? AND deleted = 0
        """, (vector_id,))

        row = cursor.fetchone()
        if row:
            return {
                "id": row["chunk_id"],
                "content": row["content"],
                "file": row["file"],
                "lines": row["lines"],
                "language": row["language"],
                "chunk_type": row["chunk_type"],
                "content_hash": row["content_hash"],
                "indexed_at": row["indexed_at"]
            }
        return None

    def get_by_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all chunks for a file"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM chunks WHERE file = ? AND deleted = 0
        """, (file_path,))

        return [dict(row) for row in cursor.fetchall()]

    def delete_by_file(self, file_path: str) -> int:
        """
        Mark chunks as deleted for a file.

        Args:
            file_path: Path to file

        Returns:
            Number of chunks marked as deleted
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            UPDATE chunks SET deleted = 1 WHERE file = ?
        """, (file_path,))
        self.connection.commit()
        return cursor.rowcount

    def track_file(self, file_path: str, content_hash: str, chunk_count: int) -> None:
        """Track an indexed file"""
        from datetime import datetime

        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO files (file_path, content_hash, indexed_at, chunk_count)
            VALUES (?, ?, ?, ?)
        """, (file_path, content_hash, datetime.now().isoformat(), chunk_count))
        self.connection.commit()

    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Get the content hash for a tracked file"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT content_hash FROM files WHERE file_path = ?
        """, (file_path,))

        row = cursor.fetchone()
        return row["content_hash"] if row else None

    def get_indexed_files(self) -> List[Dict[str, Any]]:
        """Get list of all indexed files"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM files")
        return [dict(row) for row in cursor.fetchall()]

    def clear(self) -> None:
        """Clear all data"""
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM chunks")
        cursor.execute("DELETE FROM files")
        self.connection.commit()

    def close(self) -> None:
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None
