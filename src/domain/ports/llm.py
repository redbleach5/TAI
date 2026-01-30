"""LLM Port - interface for language model providers."""

from typing import AsyncIterator, Protocol

from pydantic import BaseModel


class LLMMessage(BaseModel):
    """Single message in a conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str


class LLMResponse(BaseModel):
    """Response from LLM (non-streaming)."""

    content: str
    model: str
    done: bool = True


class LLMPort(Protocol):
    """Interface for LLM providers (Ollama, LM Studio, etc.)."""

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a single response (non-streaming)."""
        ...

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate response with streaming (yields content chunks)."""
        ...

    async def is_available(self) -> bool:
        """Check if the LLM provider is available."""
        ...

    async def list_models(self) -> list[str]:
        """List available models."""
        ...
