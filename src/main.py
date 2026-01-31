"""Application entry point."""

from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load config, setup logging, validate models."""
    container = get_container()
    setup_logging(container.config.log_level)
    await validate_models_config(container.llm, container.config)
    yield
    # Shutdown if needed


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
async def health(request: Request):
    """Health check with LLM availability."""
    container = get_container()
    llm_available = await container.llm.is_available()
    return {
        "status": "ok",
        "service": "codegen-ai",
        "llm_provider": container.config.llm.provider,
        "llm_available": llm_available,
    }
