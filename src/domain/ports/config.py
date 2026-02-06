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
    complex: str = "qwen2.5-coder:7b"
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
        """Initialize with resolved model IDs for simple, medium, complex, and fallback."""
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
    # Optional: maximize context/throughput. None = use model defaults.
    num_ctx: int | None = None  # Context window (e.g. 32768, 131072). More = longer chats, more VRAM.
    num_predict: int | None = None  # Max tokens to generate (-1 = no limit). None = model default.


class OpenAICompatibleConfig(BaseModel):
    """LM Studio, vLLM, LocalAI - OpenAI-compatible API."""

    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""
    timeout: int = 120
    # Optional: max tokens to generate. None = server/model default.
    max_tokens: int | None = None


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
    batch_size: int = 100  # Batch size for embedding requests
    max_file_count: int = 10000  # Max files to collect during indexing


class AgentConfig(BaseModel):
    """Agent loop settings."""

    max_iterations: int = 15  # Max tool-call iterations per request (ROADMAP Part 4)


class WebSearchConfig(BaseModel):
    """Web search engines (Cherry Studio–style: SearXNG, Brave, Tavily, Google Custom Search)."""

    # Custom SearXNG instance URL (e.g. http://localhost:8080). If set, used first; else public instances.
    searxng_url: str | None = None
    # Brave Search API key (2000 free/month). Optional.
    brave_api_key: str | None = None
    # Tavily API key (app.tavily.com). Optional; when set, Tavily is included in parallel search.
    tavily_api_key: str | None = None
    # Google Custom Search: API key (Google Cloud) + Programmable Search Engine ID (cx). 100 free queries/day.
    google_api_key: str | None = None
    google_cx: str | None = None  # Search engine ID from programmablesearchengine.google.com


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
    agent: AgentConfig = AgentConfig()
    web_search: WebSearchConfig = WebSearchConfig()
    log_level: str = "INFO"
    # Log file: path relative to cwd or absolute. Empty = only stdout. Rotation when file exceeds max_mb.
    log_file: str = ""
    log_rotation_max_mb: int = 5
    log_rotation_backups: int = 3


class ConfigPort(Protocol):
    """Interface for configuration providers."""

    def get_config(self) -> AppConfig:
        """Get the full application configuration."""
        ...
