"""Chat API routes."""

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import get_chat_use_case, limiter
from src.application.chat.dto import ChatRequest, ChatResponse
from src.application.chat.use_case import ChatUseCase

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("60/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    use_case: ChatUseCase = Depends(get_chat_use_case),
) -> ChatResponse:
    """Send message and get LLM response."""
    return await use_case.execute(chat_request)


@router.get("/stream")
@limiter.limit("60/minute")
async def chat_stream_get(
    request: Request,
    message: str,
    conversation_id: str | None = None,
    use_case: ChatUseCase = Depends(get_chat_use_case),
):
    """Stream LLM response via SSE (GET - no context_files)."""
    chat_request = ChatRequest(
        message=message,
        conversation_id=conversation_id,
    )
    async def event_generator():
        async for kind, chunk in use_case.execute_stream(chat_request):
            yield {"event": kind, "data": chunk}
    return EventSourceResponse(event_generator())


@router.post("/stream")
@limiter.limit("60/minute")
async def chat_stream_post(
    request: Request,
    chat_request: ChatRequest,
    use_case: ChatUseCase = Depends(get_chat_use_case),
):
    """Stream LLM response via SSE (POST - supports context_files from IDE)."""
    async def event_generator():
        async for kind, chunk in use_case.execute_stream(chat_request):
            yield {"event": kind, "data": chunk}
    return EventSourceResponse(event_generator())
