"""FastAPI dependencies - DI container."""

from functools import lru_cache
from typing import TYPE_CHECKING, Union

from slowapi import Limiter

if TYPE_CHECKING:
    from src.application.workflow.use_case import WorkflowUseCase
from slowapi.util import get_remote_address

from src.application.chat.use_case import ChatUseCase
from src.domain.ports.config import AppConfig
from src.domain.ports.llm import LLMPort
from src.domain.services.model_router import ModelRouter
from src.infrastructure.config import load_config
from src.infrastructure.embeddings.ollama import OllamaEmbeddingsAdapter
from src.infrastructure.embeddings.openai_compatible import (
    OpenAICompatibleEmbeddingsAdapter,
)
from src.infrastructure.llm.ollama import OllamaAdapter
from src.infrastructure.llm.openai_compatible import OpenAICompatibleAdapter
from src.infrastructure.persistence.conversation_memory import ConversationMemory
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter

limiter = Limiter(key_func=get_remote_address)


@lru_cache
def get_config() -> AppConfig:
    """Load config once at startup."""
    return load_config()


def get_llm_adapter() -> Union[OllamaAdapter, OpenAICompatibleAdapter]:
    """Create LLM adapter based on config.llm.provider."""
    config = get_config()
    if config.llm.provider == "lm_studio":
        return OpenAICompatibleAdapter(config.openai_compatible)
    return OllamaAdapter(config.ollama)


def get_conversation_memory() -> ConversationMemory:
    """Create ConversationMemory with config."""
    config = get_config()
    return ConversationMemory(output_dir=config.persistence.output_dir)


def get_embeddings_adapter():
    """Create embeddings adapter based on config.llm.provider."""
    config = get_config()
    if config.llm.provider == "lm_studio":
        return OpenAICompatibleEmbeddingsAdapter(
            config.openai_compatible,
            config.embeddings,
        )
    return OllamaEmbeddingsAdapter(config.ollama, config.embeddings)


def get_rag_adapter() -> ChromaDBRAGAdapter:
    """Create ChromaDB RAG adapter with embeddings."""
    config = get_config()
    embeddings = get_embeddings_adapter()
    return ChromaDBRAGAdapter(config.rag, embeddings)


def get_model_router() -> ModelRouter:
    """Create ModelRouter with config and provider."""
    config = get_config()
    return ModelRouter(config.models, provider=config.llm.provider)


def get_chat_use_case() -> ChatUseCase:
    """Create ChatUseCase with LLM and config."""
    config = get_config()
    llm: LLMPort = get_llm_adapter()
    model_router = get_model_router()
    memory = get_conversation_memory()
    return ChatUseCase(
        llm=llm,
        model_router=model_router,
        max_context_messages=config.persistence.max_context_messages,
        memory=memory,
    )


def get_workflow_use_case() -> "WorkflowUseCase":
    """Create WorkflowUseCase with LLM, RAG and config."""
    from src.application.workflow.use_case import WorkflowUseCase

    llm: LLMPort = get_llm_adapter()
    model_router = get_model_router()
    rag = get_rag_adapter()
    return WorkflowUseCase(llm=llm, model_router=model_router, rag=rag)
