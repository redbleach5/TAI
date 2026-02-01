"""Dependency Injection Container - centralized service management."""

from functools import cached_property
from typing import TYPE_CHECKING

from src.api.store import ProjectsStore
from src.domain.ports.config import AppConfig
from src.domain.ports.llm import LLMPort
from src.domain.ports.embeddings import EmbeddingsPort
from src.domain.services.model_router import ModelRouter
from src.domain.services.model_selector import ModelSelector
from src.infrastructure.config import load_config

if TYPE_CHECKING:
    from src.application.agent.use_case import AgentUseCase
    from src.application.chat.use_case import ChatUseCase
    from src.application.workflow.use_case import WorkflowUseCase
    from src.application.improvement.use_case import SelfImprovementUseCase
    from src.infrastructure.agents.file_writer import FileWriter
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
    def model_selector(self) -> ModelSelector:
        """Model selector - auto-select by capability from available models."""
        return ModelSelector(
            llm=self.llm,
            model_router=self.model_router,
            config=self.config,
        )

    @cached_property
    def projects_store(self) -> ProjectsStore:
        """Projects store (current workspace, list of projects)."""
        return ProjectsStore()

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
    def agent_use_case(self) -> "AgentUseCase":
        """Agent use case for autonomous tool execution."""
        from src.application.agent.use_case import AgentUseCase
        ws = self.config.web_search
        return AgentUseCase(
            llm=self.llm,
            model_selector=self.model_selector,
            rag=self.rag,
            max_iterations=self.config.agent.max_iterations,
            web_search_searxng_url=ws.searxng_url,
            web_search_brave_api_key=ws.brave_api_key,
            web_search_tavily_api_key=ws.tavily_api_key,
            web_search_google_api_key=ws.google_api_key,
            web_search_google_cx=ws.google_cx,
        )

    @cached_property
    def chat_use_case(self) -> "ChatUseCase":
        """Chat use case with all dependencies."""
        from pathlib import Path
        from src.application.chat.use_case import ChatUseCase

        def _workspace_path() -> str:
            current = self.projects_store.get_current()
            return current.path if current else str(Path.cwd().resolve())

        def _is_indexed() -> bool:
            current = self.projects_store.get_current()
            return bool(current and getattr(current, "indexed", False))

        ws = self.config.web_search
        return ChatUseCase(
            llm=self.llm,
            model_selector=self.model_selector,
            max_context_messages=self.config.persistence.max_context_messages,
            memory=self.conversation_memory,
            rag=self.rag,
            agent_use_case=self.agent_use_case,
            workspace_path_getter=_workspace_path,
            is_indexed_getter=_is_indexed,
            web_search_searxng_url=ws.searxng_url,
            web_search_brave_api_key=ws.brave_api_key,
            web_search_tavily_api_key=ws.tavily_api_key,
            web_search_google_api_key=ws.google_api_key,
            web_search_google_cx=ws.google_cx,
        )
    
    @cached_property
    def workflow_use_case(self) -> "WorkflowUseCase":
        """Workflow use case for code generation."""
        from src.application.workflow.use_case import WorkflowUseCase
        return WorkflowUseCase(
            llm=self.llm,
            model_selector=self.model_selector,
            rag=self.rag,
        )
    
    @cached_property
    def file_writer(self) -> "FileWriter":
        """File writer for improvement (backup, read/write)."""
        from src.infrastructure.agents.file_writer import FileWriter
        return FileWriter()

    @cached_property
    def improvement_use_case(self) -> "SelfImprovementUseCase":
        """Self-improvement use case."""
        from pathlib import Path
        from src.application.improvement.use_case import SelfImprovementUseCase

        def _workspace_path() -> str:
            current = self.projects_store.get_current()
            return current.path if current else str(Path.cwd().resolve())

        return SelfImprovementUseCase(
            llm=self.llm,
            model_selector=self.model_selector,
            file_writer=self.file_writer,
            rag=self.rag,
            workspace_path_getter=_workspace_path,
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
