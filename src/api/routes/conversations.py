"""Conversations API - list and load saved dialogues."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_conversation_memory, limiter
from src.infrastructure.persistence.conversation_memory import ConversationMemory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
@limiter.limit("60/minute")
async def list_conversations(
    request: Request,
    memory: ConversationMemory = Depends(get_conversation_memory),
) -> list[dict]:
    """List saved conversations with id and title (from first user message)."""
    try:
        return memory.list_with_titles()
    except Exception:
        logger.exception("Failed to list conversations")
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.get("/ids")
@limiter.limit("60/minute")
async def list_conversation_ids(
    request: Request,
    memory: ConversationMemory = Depends(get_conversation_memory),
) -> list[str]:
    """List saved conversation IDs only (legacy)."""
    try:
        return memory.list_ids()
    except Exception:
        logger.exception("Failed to list conversation IDs")
        raise HTTPException(status_code=500, detail="Failed to list conversation IDs")


@router.get("/{conversation_id}")
@limiter.limit("60/minute")
async def get_conversation(
    conversation_id: str,
    request: Request,
    memory: ConversationMemory = Depends(get_conversation_memory),
) -> list[dict]:
    """Load conversation messages."""
    try:
        messages = memory.load(conversation_id)
    except Exception:
        logger.exception("Failed to load conversation %s", conversation_id)
        raise HTTPException(status_code=500, detail="Failed to load conversation")
    return [{"role": m.role, "content": m.content} for m in messages]


@router.delete("/{conversation_id}")
@limiter.limit("30/minute")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    memory: ConversationMemory = Depends(get_conversation_memory),
) -> dict:
    """Delete a conversation."""
    deleted = memory.delete(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}
