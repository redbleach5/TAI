"""Chat DTOs."""

from pydantic import BaseModel, Field

from src.domain.ports.llm import LLMMessage


class ContextFile(BaseModel):
    """File content for chat context (Cursor-like)."""

    path: str = Field(..., max_length=1024)
    content: str = Field(..., max_length=500_000)


class ChatRequest(BaseModel):
    """Request for chat completion.

    Contract: history = previous turns only (user/assistant pairs).
    Current user message is in message; backend appends it when building LLM context.
    """

    message: str = Field(..., min_length=1, max_length=100_000)
    history: list[LLMMessage] | None = None  # Previous turns only; do not include current message
    conversation_id: str | None = Field(None, max_length=100)
    mode_id: str | None = Field(None, max_length=100)  # Assistant mode (coder, researcher, etc.)
    model: str | None = Field(None, max_length=255)  # Override model (Cursor-like)
    context_files: list[ContextFile] | None = Field(None, max_length=50)  # Open files from IDE
    active_file_path: str | None = Field(None, max_length=1024)  # Path of the focused tab
    apply_edits_required: bool = True  # Agent write_file proposed only; user applies/rejects in UI


class ChatResponse(BaseModel):
    """Response from chat completion."""

    content: str
    model: str
    conversation_id: str | None = None
