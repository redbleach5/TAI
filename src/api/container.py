"""Dependency Injection Container - centralized service management."""

from functools import cached_property
from typing import TYPE_CHECKING

from src.domain.ports.config import AppConfig
from src.domain.ports.llm import LLMPort
from src.domain.ports.embeddings import EmbeddingsPort
from src.domain.services.model_router import ModelRouter
from src.infrastructure.config import load_config

if TYPE_CHECKING:
    from src.application.chat.use_case import ChatUseCase
    from src.application.workflow.use_case import WorkflowUseCase
    from src.application.improvement.use_case import SelfImprovementUseCase
    from src.infrastructure.persistence.conversation_memory import ConversationMemory
    from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter


class Container:
    """Dependency Injection Container with lazy initialization.
    
    All dependencies are created on first access and cached.
    This allows for better testability and cleaner dependency management.
    
    Usage:
        container = Container()
        chat_use_case = container.chat_use_case
    """
    
    def __init__(self, config: AppConfig | None = None):
        """Initialize container with optional config override."""
        self._config_override = config
        self._instances: dict = {}
    
    @cached_property
    def config(self) -> AppConfig:
        """Application configuration."""
        if self._config_override:
            return self._config_override
        return load_config()
    
    @cached_property
    def llm(self) -> LLMPort:
        """LLM adapter based on config provider."""
        if self.config.llm.provider == "lm_studio":
            from src.infrastructure.llm.openai_compatible import OpenAICompatibleAdapter
            return OpenAICompatibleAdapter(self.config.openai_compatible)
        
        from src.infrastructure.llm.ollama import OllamaAdapter
        return OllamaAdapter(self.config.ollama)
    
    @cached_property
    def embeddings(self) -> EmbeddingsPort:
        """Embeddings adapter based on config provider."""
        if self.config.llm.provider == "lm_studio":
            from src.infrastructure.embeddings.openai_compatible import (
                OpenAICompatibleEmbeddingsAdapter,
            )
            return OpenAICompatibleEmbeddingsAdapter(
                self.config.openai_compatible,
                self.config.embeddings,
            )
        
        from src.infrastructure.embeddings.ollama import OllamaEmbeddingsAdapter
        return OllamaEmbeddingsAdapter(
            self.config.ollama,
            self.config.embeddings,
        )
    
    @cached_property
    def model_router(self) -> ModelRouter:
        """Model router for complexity-based selection."""
        return ModelRouter(
            self.config.models,
            provider=self.config.llm.provider,
        )
    
    @cached_property
    def conversation_memory(self) -> "ConversationMemory":
        """Conversation memory for chat history."""
        from src.infrastructure.persistence.conversation_memory import ConversationMemory
        return ConversationMemory(
            output_dir=self.config.persistence.output_dir,
        )
    
    @cached_property
    def rag(self) -> "ChromaDBRAGAdapter":
        """RAG adapter for codebase search."""
        from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter
        return ChromaDBRAGAdapter(
            self.config.rag,
            self.embeddings,
        )
    
    @cached_property
    def chat_use_case(self) -> "ChatUseCase":
        """Chat use case with all dependencies."""
        from src.application.chat.use_case import ChatUseCase
        return ChatUseCase(
            llm=self.llm,
            model_router=self.model_router,
            max_context_messages=self.config.persistence.max_context_messages,
            memory=self.conversation_memory,
            rag=self.rag,
        )
    
    @cached_property
    def workflow_use_case(self) -> "WorkflowUseCase":
        """Workflow use case for code generation."""
        from src.application.workflow.use_case import WorkflowUseCase
        return WorkflowUseCase(
            llm=self.llm,
            model_router=self.model_router,
            rag=self.rag,
        )
    
    @cached_property
    def improvement_use_case(self) -> "SelfImprovementUseCase":
        """Self-improvement use case."""
        from src.application.improvement.use_case import SelfImprovementUseCase
        return SelfImprovementUseCase(
            llm=self.llm,
            model_router=self.model_router,
        )
    
    def reset(self) -> None:
        """Reset all cached instances (useful for testing)."""
        # Clear cached_property values
        for attr in list(self.__dict__.keys()):
            if not attr.startswith("_"):
                delattr(self, attr)


# Global container instance
_container: Container | None = None


def get_container() -> Container:
    """Get or create global container instance."""
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset global container (for testing)."""
    global _container
    if _container:
        _container.reset()
    _container = None
