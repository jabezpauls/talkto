from .base import BaseEmbedding
from .ollama import OllamaEmbedding
from .openai import OpenAIEmbedding

__all__ = ['BaseEmbedding', 'OllamaEmbedding', 'OpenAIEmbedding']


def get_embedding_provider(config: dict) -> BaseEmbedding:
    """Get the embedding provider based on config"""
    provider = config.get("provider", "local")
    model = config.get("model", "nomic-embed-text")
    api_key = config.get("api_key")
    base_url = config.get("base_url")

    if provider == "local" or provider == "ollama":
        return OllamaEmbedding(model=model)
    elif provider == "openai":
        return OpenAIEmbedding(model=model, api_key=api_key, base_url=base_url)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
