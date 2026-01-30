"""RAG Port - interface for retrieval-augmented generation."""

from typing import Protocol

from pydantic import BaseModel


class Chunk(BaseModel):
    """A retrieved code/document chunk."""

    content: str
    metadata: dict = {}
    score: float = 1.0


class RAGPort(Protocol):
    """Interface for RAG providers (ChromaDB, etc.)."""

    async def search(self, query: str, limit: int = 10) -> list[Chunk]:
        """Search for relevant chunks by query."""
        ...

    async def index_path(self, path: str) -> None:
        """Index a directory for RAG search."""
        ...
