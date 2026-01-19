from .base import BaseLLM
from .ollama import OllamaLLM
from .openai import OpenAILLM

__all__ = ['BaseLLM', 'OllamaLLM', 'OpenAILLM']


def get_llm_provider(config: dict) -> BaseLLM:
    """Get the LLM provider based on config"""
    provider = config.get("provider", "ollama")
    model = config.get("model", "llama3.1:8b")

    if provider == "ollama":
        return OllamaLLM(model=model)
    elif provider == "openai":
        return OpenAILLM(model=model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
