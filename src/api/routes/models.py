"""Models API - list available models and resilience stats."""

from fastapi import APIRouter, Depends, Request

from src.api.dependencies import get_llm_adapter, get_model_router, limiter
from src.domain.ports.llm import LLMPort
from src.domain.services.model_router import ModelRouter
from src.infrastructure.resilience import get_all_breakers, reset_all_breakers

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
@limiter.limit("60/minute")
async def list_models(
    request: Request,
    llm: LLMPort = Depends(get_llm_adapter),
) -> list[str]:
    """List available models from current LLM provider (Ollama or LM Studio)."""
    return await llm.list_models()


@router.get("/router/cache")
@limiter.limit("60/minute")
async def get_router_cache(
    request: Request,
    router: ModelRouter = Depends(get_model_router),
):
    """Get model router cache statistics."""
    return router.cache_info()


@router.get("/resilience")
@limiter.limit("60/minute")
async def get_resilience_stats(request: Request):
    """Get Circuit Breaker statistics for all services."""
    return {
        "circuit_breakers": get_all_breakers(),
    }


@router.post("/resilience/reset")
@limiter.limit("10/minute")
async def reset_resilience(request: Request):
    """Reset all Circuit Breakers (admin action)."""
    reset_all_breakers()
    return {"status": "ok", "message": "All circuit breakers reset"}
