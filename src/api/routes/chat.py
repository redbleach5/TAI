"""Chat API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import get_chat_use_case, limiter
from src.application.chat.dto import ChatRequest, ChatResponse
from src.application.chat.use_case import ChatUseCase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("60/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    use_case: ChatUseCase = Depends(get_chat_use_case),
) -> ChatResponse:
    """Send message and get LLM response."""
    try:
        return await use_case.execute(chat_request)
    except Exception:
        logger.exception("Chat execution failed for conversation=%s", chat_request.conversation_id)
        raise HTTPException(status_code=500, detail="Chat request failed")


@router.get("/stream")
@limiter.limit("60/minute")
async def chat_stream_get(
    request: Request,
    message: str,
    conversation_id: str | None = None,
    use_case: ChatUseCase = Depends(get_chat_use_case),
) -> EventSourceResponse:
    """Stream LLM response via SSE (GET - no context_files)."""
    chat_request = ChatRequest(
        message=message,
        conversation_id=conversation_id,
    )

    async def event_generator():
        try:
            async for kind, chunk in use_case.execute_stream(chat_request):
                yield {"event": kind, "data": chunk}
        except Exception:
            logger.exception("Chat stream failed for conversation=%s", conversation_id)
            yield {"event": "error", "data": "Stream failed"}

    return EventSourceResponse(event_generator())


@router.post("/stream")
@limiter.limit("60/minute")
async def chat_stream_post(
    request: Request,
    chat_request: ChatRequest,
    use_case: ChatUseCase = Depends(get_chat_use_case),
) -> EventSourceResponse:
    """Stream LLM response via SSE (POST - supports context_files from IDE)."""

    async def event_generator():
        try:
            async for kind, chunk in use_case.execute_stream(chat_request):
                yield {"event": kind, "data": chunk}
        except Exception:
            logger.exception(
                "Chat stream failed for conversation=%s",
                chat_request.conversation_id,
            )
            yield {"event": "error", "data": "Stream failed"}

    return EventSourceResponse(event_generator())
