"""Chat DTOs."""

from pydantic import BaseModel

from src.domain.ports.llm import LLMMessage


class ChatRequest(BaseModel):
    """Request for chat completion."""

    message: str
    history: list[LLMMessage] | None = None
    conversation_id: str | None = None
    mode_id: str | None = None  # Assistant mode (coder, researcher, etc.)


class ChatResponse(BaseModel):
    """Response from chat completion."""

    content: str
    model: str
    conversation_id: str | None = None
