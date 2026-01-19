"""
Error handling for the RAG engine.
"""

from typing import Any, Optional


class EngineError(Exception):
    """Base exception for engine errors"""

    def __init__(self, code: str, message: str, details: Optional[Any] = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class ConfigurationError(EngineError):
    """Configuration-related errors"""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__("CONFIGURATION_ERROR", message, details)


class IndexingError(EngineError):
    """Indexing-related errors"""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__("INDEXING_ERROR", message, details)


class EmbeddingError(EngineError):
    """Embedding-related errors"""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__("EMBEDDING_ERROR", message, details)


class RetrievalError(EngineError):
    """Retrieval-related errors"""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__("RETRIEVAL_ERROR", message, details)


class LLMError(EngineError):
    """LLM-related errors"""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__("LLM_ERROR", message, details)


class OllamaNotRunningError(EngineError):
    """Ollama service not running"""

    def __init__(self):
        super().__init__(
            "OLLAMA_NOT_RUNNING",
            "Ollama is not running. Please start Ollama and try again.",
            {"help": "Run 'ollama serve' to start the Ollama service"}
        )


class ModelNotFoundError(EngineError):
    """Model not found"""

    def __init__(self, model: str):
        super().__init__(
            "MODEL_NOT_FOUND",
            f"Model '{model}' not found.",
            {"help": f"Run 'ollama pull {model}' to download the model"}
        )


class NoIndexError(EngineError):
    """No index exists"""

    def __init__(self, path: str):
        super().__init__(
            "NO_INDEX",
            f"No index found for path: {path}",
            {"help": "Run 'rag index <path>' to create an index"}
        )
