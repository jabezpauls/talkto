from .base import BaseEmbedding
from .ollama import OllamaEmbedding
from .openai import OpenAIEmbedding

__all__ = ['BaseEmbedding', 'OllamaEmbedding', 'OpenAIEmbedding']


def get_embedding_provider(config: dict) -> BaseEmbedding:
    """Get the embedding provider based on config"""
    provider = config.get("provider", "local")
    model = config.get("model", "nomic-embed-text")

    if provider == "local" or provider == "ollama":
        return OllamaEmbedding(model=model)
    elif provider == "openai":
        return OpenAIEmbedding(model=model)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
