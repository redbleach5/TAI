"""Models API - list available models from current provider."""

from fastapi import APIRouter, Depends, Request

from src.api.dependencies import get_llm_adapter, limiter
from src.domain.ports.llm import LLMPort

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
@limiter.limit("60/minute")
async def list_models(
    request: Request,
    llm: LLMPort = Depends(get_llm_adapter),
) -> list[str]:
    """List available models from current LLM provider (Ollama or LM Studio)."""
    return await llm.list_models()
