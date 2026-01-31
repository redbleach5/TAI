"""Chat DTOs."""

from pydantic import BaseModel

from src.domain.ports.llm import LLMMessage


class ContextFile(BaseModel):
    """File content for chat context (Cursor-like)."""
    path: str
    content: str


class ChatRequest(BaseModel):
    """Request for chat completion."""

    message: str
    history: list[LLMMessage] | None = None
    conversation_id: str | None = None
    mode_id: str | None = None  # Assistant mode (coder, researcher, etc.)
    model: str | None = None  # Override model (Cursor-like)
    context_files: list[ContextFile] | None = None  # Open files from IDE


class ChatResponse(BaseModel):
    """Response from chat completion."""

    content: str
    model: str
    conversation_id: str | None = None
