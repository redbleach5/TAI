"""Application entry point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.container import get_container
from src.api.dependencies import limiter
from src.api.routes.analyze import router as analyze_router
from src.api.routes.assistant import router as assistant_router
from src.api.routes.chat import router as chat_router
from src.api.routes.code import router as code_router
from src.api.routes.config import router as config_router
from src.api.routes.conversations import router as conversations_router
from src.api.routes.files import router as files_router
from src.api.routes.git import router as git_router
from src.api.routes.improve import router as improve_router
from src.api.routes.models import router as models_router
from src.api.routes.projects import router as projects_router
from src.api.routes.rag import router as rag_router
from src.api.routes.terminal import router as terminal_router
from src.api.routes.workflow import router as workflow_router
from src.api.routes.workspace import router as workspace_router
from src.infrastructure.config.model_validator import validate_models_config
from src.shared.logging import setup_logging

log = structlog.get_logger()


def _apply_logging_config(container):
    """Apply logging from container config (stdout + optional file)."""
    c = container.config
    setup_logging(
        level=c.log_level,
        file_path=c.log_file or "",
        rotation_max_mb=c.log_rotation_max_mb,
        rotation_backups=c.log_rotation_backups,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load config, setup logging, validate models, warm model selector cache."""
    container = get_container()
    _apply_logging_config(container)
    log.info("startup_begin", llm_provider=container.config.llm.provider)
    await validate_models_config(container.llm, container.config)
    try:
        await container.model_selector.warm_cache()
        log.info("model_selector_cache_warmed")
    except Exception as e:  # noqa: BLE001
        # LLM may be down at startup; first request will populate cache
        log.warning("model_selector_cache_skip", reason=str(e))
    log.info("startup_complete")
    yield
    # Shutdown: close shared resources
    log.info("shutdown_begin")
    from src.infrastructure.services.http_pool import HTTPPool

    await HTTPPool.reset()
    if hasattr(container.llm, "close"):
        try:
            await container.llm.close()
        except Exception:  # noqa: BLE001
            log.debug("llm_close_error", exc_info=True)
    log.info("shutdown_complete")


# Create app
app = FastAPI(
    title="CodeGen AI",
    version="0.1.0",
    description="Local AI code generation system - Cursor alternative",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
container = get_container()
app.add_middleware(
    CORSMiddleware,
    allow_origins=container.config.security.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(analyze_router)
app.include_router(assistant_router)
app.include_router(chat_router)
app.include_router(code_router)
app.include_router(config_router)
app.include_router(conversations_router)
app.include_router(files_router)
app.include_router(git_router)
app.include_router(improve_router)
app.include_router(models_router)
app.include_router(projects_router)
app.include_router(rag_router)
app.include_router(terminal_router)
app.include_router(workflow_router)
app.include_router(workspace_router)


@app.get("/health")
@limiter.limit("100/minute")
async def health(request: Request) -> dict:
    """Health check with LLM availability."""
    container = get_container()
    llm_available = await container.llm.is_available()
    return {
        "status": "ok",
        "service": "codegen-ai",
        "llm_provider": container.config.llm.provider,
        "llm_available": llm_available,
    }
