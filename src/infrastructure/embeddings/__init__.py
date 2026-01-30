"""Embeddings adapters - Ollama, OpenAI-compatible."""

from src.infrastructure.embeddings.ollama import OllamaEmbeddingsAdapter
from src.infrastructure.embeddings.openai_compatible import (
    OpenAICompatibleEmbeddingsAdapter,
)

__all__ = ["OllamaEmbeddingsAdapter", "OpenAICompatibleEmbeddingsAdapter"]
