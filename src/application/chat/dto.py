"""Chat DTOs."""

from pydantic import BaseModel

from src.domain.ports.llm import LLMMessage


class ContextFile(BaseModel):
    """File content for chat context (Cursor-like)."""
    path: str
    content: str


class ChatRequest(BaseModel):
    """Request for chat completion.

    Contract: history = previous turns only (user/assistant pairs).
    Current user message is in message; backend appends it when building LLM context.
    """

    message: str
    history: list[LLMMessage] | None = None  # Previous turns only; do not include current message
    conversation_id: str | None = None
    mode_id: str | None = None  # Assistant mode (coder, researcher, etc.)
    model: str | None = None  # Override model (Cursor-like)
    context_files: list[ContextFile] | None = None  # Open files from IDE (Cursor-like — model sees these automatically)
    active_file_path: str | None = None  # Path of the focused tab — "current file" for the model


class ChatResponse(BaseModel):
    """Response from chat completion."""

    content: str
    model: str
    conversation_id: str | None = None
