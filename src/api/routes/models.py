"""Models API - list available models and resilience stats."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.container import get_container
from src.api.dependencies import get_llm_adapter, get_model_router, limiter
from src.domain.ports.llm import LLMPort
from src.domain.services.model_router import ModelRouter
from src.infrastructure.resilience import get_all_breakers, reset_all_breakers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


def _get_llm_for_provider(provider: str) -> LLMPort:
    """Get LLM adapter for a specific provider (for model listing)."""
    container = get_container()
    if provider == "lm_studio":
        from src.infrastructure.llm.openai_compatible import OpenAICompatibleAdapter

        return OpenAICompatibleAdapter(container.config.openai_compatible)
    from src.infrastructure.llm.ollama import OllamaAdapter

    return OllamaAdapter(container.config.ollama)


@router.get("")
@limiter.limit("60/minute")
async def list_models(
    request: Request,
    provider: str | None = None,
    llm: LLMPort = Depends(get_llm_adapter),
) -> list[str]:
    """List available models from LLM provider.

    provider: Optional. "ollama" or "lm_studio" to fetch models for that provider.
    If omitted, uses current configured provider.
    """
    if provider in ("ollama", "lm_studio"):
        llm = _get_llm_for_provider(provider)
    try:
        return await llm.list_models()
    except Exception:
        logger.exception("Failed to list models for provider=%s", provider)
        raise HTTPException(status_code=502, detail="Failed to list models from LLM provider")


@router.get("/router/cache")
@limiter.limit("60/minute")
async def get_router_cache(
    request: Request,
    router: ModelRouter = Depends(get_model_router),
) -> dict:
    """Get model router cache statistics."""
    return router.cache_info()


@router.get("/resilience")
@limiter.limit("60/minute")
async def get_resilience_stats(request: Request) -> dict:
    """Get Circuit Breaker statistics for all services."""
    return {
        "circuit_breakers": get_all_breakers(),
    }


@router.post("/resilience/reset")
@limiter.limit("10/minute")
async def reset_resilience(request: Request) -> dict:
    """Reset all Circuit Breakers (admin action)."""
    reset_all_breakers()
    return {"status": "ok", "message": "All circuit breakers reset"}
