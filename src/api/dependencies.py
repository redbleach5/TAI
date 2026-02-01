"""FastAPI dependencies - uses Container for DI."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.container import get_container
from src.api.store import ProjectsStore
from src.application.chat.use_case import ChatUseCase
from src.application.workflow.use_case import WorkflowUseCase
from src.application.improvement.use_case import SelfImprovementUseCase
from src.domain.ports.config import AppConfig
from src.domain.ports.llm import LLMPort
from src.domain.services.model_router import ModelRouter
from src.domain.services.model_selector import ModelSelector
from src.infrastructure.persistence.conversation_memory import ConversationMemory
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


def get_store() -> ProjectsStore:
    """Get projects store from container."""
    return get_container().projects_store


def get_config() -> AppConfig:
    """Get application configuration."""
    return get_container().config


def get_llm_adapter() -> LLMPort:
    """Get LLM adapter."""
    return get_container().llm


def get_conversation_memory() -> ConversationMemory:
    """Get conversation memory."""
    return get_container().conversation_memory


def get_model_router() -> ModelRouter:
    """Get model router."""
    return get_container().model_router


def get_model_selector() -> ModelSelector:
    """Get model selector (auto-select by capability)."""
    return get_container().model_selector


def get_chat_use_case() -> ChatUseCase:
    """Get chat use case."""
    return get_container().chat_use_case


def get_workflow_use_case() -> WorkflowUseCase:
    """Get workflow use case."""
    return get_container().workflow_use_case


def get_improvement_use_case() -> SelfImprovementUseCase:
    """Get self-improvement use case."""
    return get_container().improvement_use_case


def get_rag_adapter() -> ChromaDBRAGAdapter:
    """Get RAG adapter."""
    return get_container().rag
