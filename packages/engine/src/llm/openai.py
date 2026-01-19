"""
OpenAI LLM provider.
"""

import os
import logging
from typing import Generator

from .base import BaseLLM
from ..protocol.errors import LLMError, ConfigurationError

logger = logging.getLogger(__name__)


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider"""

    def __init__(self, model: str = "gpt-4.1-mini", api_key: str = None):
        super().__init__(model)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None

        if not self.api_key:
            raise ConfigurationError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )

    @property
    def client(self):
        """Lazy-load OpenAI client"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise LLMError(
                    "openai package not installed. Install with: pip install openai"
                )
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000
    ) -> str:
        """Generate a response"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens
            )
            return response.choices[0].message.content

        except Exception as e:
            raise LLMError(f"Failed to generate response: {e}")

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """Generate a streaming response"""
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise LLMError(f"Failed to generate streaming response: {e}")
