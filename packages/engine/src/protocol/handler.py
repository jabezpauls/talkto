"""
Command handler for routing requests to appropriate handlers.
"""

import logging
from typing import Any, Dict, Generator

from .messages import Request
from .errors import EngineError

logger = logging.getLogger(__name__)


class CommandHandler:
    """Routes commands to appropriate handlers"""

    def __init__(self):
        self._indexer = None
        self._retriever = None
        self._chat_engine = None
        self._config = self._load_config()
        self._indexed_path = None  # Track the last indexed path

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration"""
        # Default configuration
        return {
            "embedding": {
                "provider": "local",
                "model": "nomic-embed-text"
            },
            "llm": {
                "provider": "ollama",
                "model": "llama3.1:8b"
            },
            "index": {
                "include": ["**/*"],
                "exclude": ["node_modules/**", ".git/**", "dist/**", "__pycache__/**"],
                "max_file_size": 5 * 1024 * 1024  # 5MB
            }
        }

    @property
    def indexer(self):
        """Lazy-load indexer"""
        if self._indexer is None:
            from ..indexing.pipeline import IndexingPipeline
            self._indexer = IndexingPipeline(self._config)
        return self._indexer

    def get_chat_engine(self, project_path: str = None):
        """Get chat engine for a specific project path"""
        path = project_path or self._indexed_path
        if self._chat_engine is None or path != self._indexed_path:
            from ..chat.engine import RAGChatEngine
            self._chat_engine = RAGChatEngine(self._config, project_path=path)
        return self._chat_engine

    def handle(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request and return response data"""
        request = Request.from_dict(request_data)
        action = request.action

        if action == "health":
            return self._handle_health(request)
        elif action == "index":
            return self._handle_index(request)
        elif action == "query":
            return self._handle_query(request)
        elif action == "config":
            return self._handle_config(request)
        else:
            raise EngineError("UNKNOWN_ACTION", f"Unknown action: {action}")

    def handle_streaming(self, request_data: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """Handle a streaming request"""
        request = Request.from_dict(request_data)

        if request.action == "query":
            yield from self._handle_query_streaming(request)
        else:
            # Fall back to non-streaming
            result = self.handle(request_data)
            yield {"type": "done", "content": None, "source": None, "data": result}

    def _handle_health(self, request: Request) -> Dict[str, Any]:
        """Handle health check"""
        return {
            "status": "healthy",
            "version": "0.1.0"
        }

    def _handle_index(self, request: Request) -> Dict[str, Any]:
        """Handle index command"""
        path = request.path
        if not path:
            raise EngineError("MISSING_PATH", "Path is required for indexing")

        # Store the indexed path for subsequent queries
        from pathlib import Path
        self._indexed_path = str(Path(path).resolve())

        options = request.options
        result = self.indexer.index(
            path=path,
            include=options.get("include"),
            exclude=options.get("exclude"),
            force=options.get("force", False)
        )

        return result.to_dict()

    def _handle_query(self, request: Request) -> Dict[str, Any]:
        """Handle query command (non-streaming)"""
        query = request.query
        if not query:
            raise EngineError("MISSING_QUERY", "Query is required")

        options = request.options
        chat_engine = self.get_chat_engine()
        result = chat_engine.query(
            question=query,
            top_k=options.get("topK", 5),
            stream=False
        )

        return result.to_dict()

    def _handle_query_streaming(self, request: Request) -> Generator[Dict[str, Any], None, None]:
        """Handle query command (streaming)"""
        query = request.query
        if not query:
            raise EngineError("MISSING_QUERY", "Query is required")

        options = request.options
        chat_engine = self.get_chat_engine()

        for chunk in chat_engine.query_streaming(
            question=query,
            top_k=options.get("topK", 5)
        ):
            yield chunk

    def _handle_config(self, request: Request) -> Dict[str, Any]:
        """Handle config command"""
        options = request.options
        operation = options.get("operation", "get")

        if operation == "get":
            key = options.get("key")
            if key:
                # Get specific key
                parts = key.split(".")
                value = self._config
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        return {"value": None}
                return {"value": value}
            else:
                # Get all config
                return {"config": self._config}

        elif operation == "set":
            key = options.get("key")
            value = options.get("value")
            if not key:
                raise EngineError("MISSING_KEY", "Key is required for set operation")

            # Set nested value
            parts = key.split(".")
            target = self._config
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = value

            # Reset lazy-loaded components to pick up new config
            self._indexer = None
            self._chat_engine = None

            return {"success": True, "key": key, "value": value}

        elif operation == "set_all":
            new_config = options.get("config", {})
            # Merge new config with existing (deep merge)
            for key, value in new_config.items():
                if isinstance(value, dict) and key in self._config:
                    self._config[key].update(value)
                else:
                    self._config[key] = value

            # Reset lazy-loaded components to pick up new config
            self._indexer = None
            self._chat_engine = None

            logger.info(f"Config updated: {self._config}")
            return {"success": True, "config": self._config}

        else:
            raise EngineError("INVALID_OPERATION", f"Unknown config operation: {operation}")
