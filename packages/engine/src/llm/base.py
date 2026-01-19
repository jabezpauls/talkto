"""
Base LLM interface.
"""

from abc import ABC, abstractmethod
from typing import Generator


class BaseLLM(ABC):
    """Base class for LLM providers"""

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000
    ) -> str:
        """
        Generate a response.

        Args:
            system_prompt: System message
            user_prompt: User message
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        pass

    @abstractmethod
    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response.

        Args:
            system_prompt: System message
            user_prompt: User message
            max_tokens: Maximum tokens to generate

        Yields:
            Generated tokens
        """
        pass
