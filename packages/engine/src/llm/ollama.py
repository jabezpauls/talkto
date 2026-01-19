"""
Ollama LLM provider.
"""

import logging
from typing import Generator

from .base import BaseLLM
from ..protocol.errors import OllamaNotRunningError, ModelNotFoundError, LLMError

logger = logging.getLogger(__name__)


class OllamaLLM(BaseLLM):
    """Ollama LLM provider"""

    def __init__(self, model: str = "llama3.1:8b", base_url: str = None):
        super().__init__(model)
        self.base_url = base_url or "http://localhost:11434"
        self._client = None

    @property
    def client(self):
        """Lazy-load Ollama client"""
        if self._client is None:
            try:
                import ollama
                self._client = ollama.Client(host=self.base_url)
            except ImportError:
                raise LLMError("ollama package not installed")
        return self._client

    def _check_connection(self):
        """Check if Ollama is running"""
        try:
            self.client.list()
        except Exception as e:
            if "Connection refused" in str(e) or "connection" in str(e).lower():
                raise OllamaNotRunningError()
            raise LLMError(f"Failed to connect to Ollama: {e}")

    def _ensure_model(self):
        """Ensure the model is available"""
        try:
            models = self.client.list()
            model_names = [m.model for m in models.models]

            # Check if model exists (with or without tag)
            model_base = self.model.split(':')[0]
            if not any(model_base in name for name in model_names):
                logger.info(f"Model {self.model} not found, pulling...")
                self.client.pull(self.model)

        except Exception as e:
            if "not found" in str(e).lower():
                raise ModelNotFoundError(self.model)
            raise

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000
    ) -> str:
        """Generate a response"""
        self._check_connection()
        self._ensure_model()

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={"num_predict": max_tokens}
            )
            return response.message.content

        except Exception as e:
            raise LLMError(f"Failed to generate response: {e}")

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """Generate a streaming response"""
        self._check_connection()
        self._ensure_model()

        try:
            stream = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={"num_predict": max_tokens},
                stream=True
            )

            for chunk in stream:
                if chunk.message.content:
                    yield chunk.message.content

        except Exception as e:
            raise LLMError(f"Failed to generate streaming response: {e}")
