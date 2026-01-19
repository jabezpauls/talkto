"""
RAG Chat Engine with source citations and "I don't know" discipline.
"""

import logging
from typing import Dict, Any, Generator, List, Optional
from pathlib import Path

from ..retrieval import Retriever
from ..vectorstore import FAISSStore
from ..embeddings import get_embedding_provider
from ..llm import get_llm_provider
from ..protocol.messages import QueryResult, Source
from .prompts import RAG_SYSTEM_PROMPT, build_context_prompt

logger = logging.getLogger(__name__)


class RAGChatEngine:
    """RAG chat with strict source discipline"""

    def __init__(self, config: Dict[str, Any], project_path: str = None):
        """
        Initialize RAG chat engine.

        Args:
            config: Configuration dict with embedding, llm, and storage settings
            project_path: Path to the indexed project
        """
        self.config = config
        self.project_path = project_path
        self.max_context_tokens = 4000
        self._retriever: Optional[Retriever] = None
        self._llm = None

    def _get_index_path(self) -> str:
        """Get the index path for the project"""
        from os.path import expanduser, join
        import hashlib

        storage_path = expanduser("~/.talkto/indexes")

        # Use the project path if provided, otherwise fall back to cwd
        if self.project_path:
            path_hash = hashlib.sha256(self.project_path.encode()).hexdigest()[:16]
        else:
            import os
            cwd = os.getcwd()
            path_hash = hashlib.sha256(cwd.encode()).hexdigest()[:16]

        return join(storage_path, path_hash)

    @property
    def retriever(self) -> Retriever:
        """Lazy-load retriever"""
        if self._retriever is None:
            index_path = self._get_index_path()

            # Get embedding provider
            embedding_config = self.config.get("embedding", {})
            embedding = get_embedding_provider(embedding_config)

            # Create vector store
            vector_store = FAISSStore(
                index_path=index_path,
                dimension=embedding.dimension
            )

            self._retriever = Retriever(
                vector_store=vector_store,
                embedding=embedding
            )

        return self._retriever

    @property
    def llm(self):
        """Lazy-load LLM"""
        if self._llm is None:
            llm_config = self.config.get("llm", {})
            self._llm = get_llm_provider(llm_config)
        return self._llm

    def query(
        self,
        question: str,
        top_k: int = 5,
        stream: bool = False
    ) -> QueryResult:
        """
        Answer a question using RAG.

        Args:
            question: User's question
            top_k: Number of chunks to retrieve
            stream: Enable streaming response (ignored, use query_streaming)

        Returns:
            QueryResult with answer and sources
        """
        logger.info(f"Processing query: {question[:100]}...")

        # 1. Retrieve relevant chunks
        retrieved = self.retriever.search(question, top_k=top_k)

        if not retrieved:
            return self._no_context_response()

        # 2. Build context-aware prompt
        context = self._build_context(retrieved)
        prompt = build_context_prompt(question, context)

        # 3. Generate answer
        response = self.llm.generate(
            system_prompt=RAG_SYSTEM_PROMPT,
            user_prompt=prompt
        )

        return QueryResult(
            answer=response,
            sources=self._format_sources(retrieved),
            has_answer=not self._is_no_answer(response)
        )

    def query_streaming(
        self,
        question: str,
        top_k: int = 5
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Answer a question with streaming response.

        Args:
            question: User's question
            top_k: Number of chunks to retrieve

        Yields:
            Stream chunks with type, content, and source
        """
        logger.info(f"Processing streaming query: {question[:100]}...")

        # 1. Retrieve relevant chunks
        retrieved = self.retriever.search(question, top_k=top_k)

        if not retrieved:
            yield {"type": "token", "content": "I don't have enough information in the indexed documents to answer this question."}
            yield {"type": "done"}
            return

        # 2. Build context-aware prompt
        context = self._build_context(retrieved)
        prompt = build_context_prompt(question, context)

        # 3. Generate streaming answer
        for token in self.llm.generate_stream(
            system_prompt=RAG_SYSTEM_PROMPT,
            user_prompt=prompt
        ):
            yield {"type": "token", "content": token}

        # 4. Yield sources at the end
        for source in self._format_sources(retrieved):
            yield {"type": "source", "source": source}

        yield {"type": "done"}

    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Assemble context from retrieved chunks"""
        context_parts = []
        total_tokens = 0

        for chunk in chunks:
            chunk_text = f"[Source: {chunk['file']}"
            if chunk.get('lines'):
                chunk_text += f", lines {chunk['lines']}"
            chunk_text += f"]\n{chunk['content']}\n"

            chunk_tokens = len(chunk_text) // 4  # Rough token estimate
            if total_tokens + chunk_tokens > self.max_context_tokens:
                break

            context_parts.append(chunk_text)
            total_tokens += chunk_tokens

        return "\n---\n".join(context_parts)

    def _format_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format sources for response"""
        return [
            {
                "file": chunk["file"],
                "lines": chunk.get("lines"),
                "relevance": round(chunk.get("score", 0), 3),
                "snippet": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"]
            }
            for chunk in chunks
        ]

    def _no_context_response(self) -> QueryResult:
        """Response when no relevant context found"""
        return QueryResult(
            answer="I don't have enough information in the indexed documents to answer this question.",
            sources=[],
            has_answer=False
        )

    def _is_no_answer(self, response: str) -> bool:
        """Check if response indicates lack of information"""
        no_answer_phrases = [
            "i don't have",
            "i don't know",
            "not enough information",
            "cannot find",
            "no information",
            "not mentioned"
        ]
        response_lower = response.lower()
        return any(phrase in response_lower for phrase in no_answer_phrases)
