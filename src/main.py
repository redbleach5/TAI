"""Application entry point."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.dependencies import get_config, get_llm_adapter, limiter
from src.api.routes.chat import router as chat_router
from src.api.routes.code import router as code_router
from src.api.routes.config import router as config_router
from src.api.routes.conversations import router as conversations_router
from src.api.routes.files import router as files_router
from src.api.routes.git import router as git_router
from src.api.routes.improve import router as improve_router
from src.api.routes.models import router as models_router
from src.api.routes.rag import router as rag_router
from src.api.routes.terminal import router as terminal_router
from src.api.routes.workflow import router as workflow_router
from src.domain.ports.llm import LLMPort
from src.shared.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load config, setup logging."""
    config = get_config()
    setup_logging(config.log_level)
    yield
    # Shutdown if needed


app = FastAPI(
    title="CodeGen AI",
    version="0.1.0",
    description="Local AI code generation system - Cursor alternative",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.security.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(code_router)
app.include_router(config_router)
app.include_router(conversations_router)
app.include_router(files_router)
app.include_router(git_router)
app.include_router(improve_router)
app.include_router(models_router)
app.include_router(rag_router)
app.include_router(terminal_router)
app.include_router(workflow_router)


@app.get("/health")
@limiter.limit("100/minute")
async def health(
    request: Request,
    llm: LLMPort = Depends(get_llm_adapter),
):
    """Health check with LLM availability."""
    llm_available = await llm.is_available()
    provider = get_config().llm.provider
    return {
        "status": "ok",
        "service": "codegen-ai",
        "llm_provider": provider,
        "llm_available": llm_available,
    }
