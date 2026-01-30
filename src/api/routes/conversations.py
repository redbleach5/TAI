"""Conversations API - list and load saved dialogues."""

from fastapi import APIRouter, Depends, Request

from src.api.dependencies import get_conversation_memory, limiter
from src.infrastructure.persistence.conversation_memory import ConversationMemory

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
@limiter.limit("60/minute")
async def list_conversations(
    request: Request,
    memory: ConversationMemory = Depends(get_conversation_memory),
) -> list[str]:
    """List saved conversation IDs."""
    return memory.list_ids()


@router.get("/{conversation_id}")
@limiter.limit("60/minute")
async def get_conversation(
    conversation_id: str,
    request: Request,
    memory: ConversationMemory = Depends(get_conversation_memory),
) -> list[dict]:
    """Load conversation messages."""
    messages = memory.load(conversation_id)
    return [{"role": m.role, "content": m.content} for m in messages]
