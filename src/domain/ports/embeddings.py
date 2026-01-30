"""Embeddings Port - interface for embedding providers."""

from typing import Protocol


class EmbeddingsPort(Protocol):
    """Interface for embedding providers (Ollama, LM Studio, etc.)."""

    async def embed(self, text: str) -> list[float]:
        """Embed a single text. Returns vector."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Returns list of vectors."""
        ...
