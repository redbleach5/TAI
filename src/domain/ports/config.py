"""Config Port - interface for configuration access."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class ProviderModelSet(BaseModel):
    """Model IDs per complexity for a specific provider. All optional — merge with defaults."""

    simple: str | None = None
    medium: str | None = None
    complex: str | None = None
    fallback: str | None = None


class ModelConfig(BaseModel):
    """Model selection by task complexity. Provider-agnostic defaults + per-provider overrides."""

    simple: str = "qwen2.5-coder:7b"
    medium: str = "qwen2.5-coder:7b"
    complex: str = "qwen2.5-coder:32b"
    fallback: str = "qwen2.5-coder:7b"
    # Per-provider overrides. Keys: provider name (lm_studio, ollama, openai, etc).
    overrides: dict[str, ProviderModelSet] = {}

    model_config = ConfigDict(extra="ignore")

    def get_models_for_provider(self, provider: str) -> "ResolvedModelSet":
        """Resolve model IDs for provider. Uses overrides when present, else defaults."""
        base = ResolvedModelSet(
            simple=self.simple,
            medium=self.medium,
            complex=self.complex,
            fallback=self.fallback,
        )
        if provider not in self.overrides:
            return base
        o = self.overrides[provider]
        return ResolvedModelSet(
            simple=o.simple if o.simple is not None else base.simple,
            medium=o.medium if o.medium is not None else base.medium,
            complex=o.complex if o.complex is not None else base.complex,
            fallback=o.fallback if o.fallback is not None else base.fallback,
        )


class ResolvedModelSet:
    """Resolved model IDs for a provider. Immutable."""

    __slots__ = ("simple", "medium", "complex", "fallback")

    def __init__(
        self,
        simple: str,
        medium: str,
        complex: str,
        fallback: str,
    ) -> None:
        self.simple = simple
        self.medium = medium
        self.complex = complex
        self.fallback = fallback


class LLMConfig(BaseModel):
    """LLM provider selection."""

    provider: str = "ollama"  # "ollama" | "lm_studio"


class OllamaConfig(BaseModel):
    """Ollama connection configuration."""

    host: str = "http://localhost:11434"
    timeout: int = 120
    pool_size: int = 4


class OpenAICompatibleConfig(BaseModel):
    """LM Studio, vLLM, LocalAI - OpenAI-compatible API."""

    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""
    timeout: int = 120


class EmbeddingsConfig(BaseModel):
    """Embeddings for RAG."""

    provider: str = "auto"
    model: str = "nomic-embed-text"


class SecurityConfig(BaseModel):
    """Security settings."""

    rate_limit_requests_per_minute: int = 100
    cors_origins: list[str] = ["http://localhost:5173"]


class PersistenceConfig(BaseModel):
    """Persistence settings."""

    output_dir: str = "output"
    max_context_messages: int = 20


class RAGConfig(BaseModel):
    """RAG (ChromaDB) settings."""

    chromadb_path: str = "output/chromadb"
    collection_name: str = "codebase"
    chunk_size: int = 500
    chunk_overlap: int = 50


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000


class AppConfig(BaseModel):
    """Full application configuration."""

    server: ServerConfig = ServerConfig()
    llm: LLMConfig = LLMConfig()
    ollama: OllamaConfig = OllamaConfig()
    openai_compatible: OpenAICompatibleConfig = OpenAICompatibleConfig()
    models: ModelConfig = ModelConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    security: SecurityConfig = SecurityConfig()
    persistence: PersistenceConfig = PersistenceConfig()
    rag: RAGConfig = RAGConfig()
    log_level: str = "INFO"


class ConfigPort(Protocol):
    """Interface for configuration providers."""

    def get_config(self) -> AppConfig:
        """Get the full application configuration."""
        ...
