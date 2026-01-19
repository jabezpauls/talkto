"""
Message dataclasses for the RAG engine protocol.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from datetime import datetime


@dataclass
class ChunkMetadata:
    """Metadata for a chunk"""
    file: str
    lines: Optional[str] = None
    language: str = "text"
    chunk_type: str = "text"  # text, code, function, class
    content_hash: str = ""
    indexed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "lines": self.lines,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "content_hash": self.content_hash,
            "indexed_at": self.indexed_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkMetadata":
        return cls(
            file=data.get("file", ""),
            lines=data.get("lines"),
            language=data.get("language", "text"),
            chunk_type=data.get("chunk_type", "text"),
            content_hash=data.get("content_hash", ""),
            indexed_at=data.get("indexed_at", datetime.now().isoformat())
        )


@dataclass
class Chunk:
    """A chunk of indexed content"""
    id: str
    content: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chunk":
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            metadata=ChunkMetadata.from_dict(data.get("metadata", {}))
        )


@dataclass
class Request:
    """Incoming request from CLI"""
    id: str
    action: str
    timestamp: str
    path: Optional[str] = None
    query: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Request":
        return cls(
            id=data.get("id", ""),
            action=data.get("action", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            path=data.get("path"),
            query=data.get("query"),
            options=data.get("options", {})
        )


@dataclass
class Response:
    """Response to send to CLI"""
    id: str
    status: str  # success, error, streaming
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    action: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "status": self.status,
            "timestamp": self.timestamp,
        }
        if self.action:
            result["action"] = self.action
        if self.data:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class IndexResult:
    """Result of indexing operation"""
    files_processed: int = 0
    files_skipped: int = 0
    chunks_created: int = 0
    duration: int = 0  # milliseconds
    errors: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filesProcessed": self.files_processed,
            "filesSkipped": self.files_skipped,
            "chunksCreated": self.chunks_created,
            "duration": self.duration,
            "errors": self.errors
        }


@dataclass
class QueryResult:
    """Result of a query"""
    answer: str
    sources: List[Dict[str, Any]]
    has_answer: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "hasAnswer": self.has_answer
        }


@dataclass
class Source:
    """A source reference in query results"""
    file: str
    lines: Optional[str] = None
    relevance: float = 0.0
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "lines": self.lines,
            "relevance": round(self.relevance, 3),
            "snippet": self.snippet
        }
