"""TOML configuration loader with env overrides."""

import logging
import os
import tomllib
from pathlib import Path

from src.domain.ports.config import (
    AgentConfig,
    AppConfig,
    EmbeddingsConfig,
    LLMConfig,
    ModelConfig,
    OllamaConfig,
    OpenAICompatibleConfig,
    PersistenceConfig,
    ProviderModelSet,
    RAGConfig,
    SecurityConfig,
    ServerConfig,
    WebSearchConfig,
)

logger = logging.getLogger(__name__)


def _load_toml(path: Path) -> dict:
    """Load TOML file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def _load_models_config(raw: dict) -> ModelConfig:
    """Load ModelConfig with per-provider overrides from nested TOML."""
    overrides_raw = {k: v for k, v in raw.items() if isinstance(v, dict)}
    defaults_raw = {k: v for k, v in raw.items() if k not in overrides_raw and isinstance(v, str)}
    overrides = {k: ProviderModelSet(**(v or {})) for k, v in overrides_raw.items()}
    return ModelConfig(overrides=overrides, **defaults_raw)


def _apply_env_overrides(config: dict) -> dict:
    """Apply environment variable overrides."""
    if provider := os.getenv("LLM_PROVIDER"):
        config.setdefault("llm", {})["provider"] = provider
    if host := os.getenv("OLLAMA_HOST"):
        config.setdefault("ollama", {})["host"] = host
    if base_url := os.getenv("OPENAI_BASE_URL"):
        config.setdefault("openai_compatible", {})["base_url"] = base_url
    if port := os.getenv("PORT"):
        try:
            config.setdefault("server", {})["port"] = int(port)
        except ValueError:
            logger.warning("Invalid PORT env value: %r, ignoring", port)
    if level := os.getenv("LOG_LEVEL"):
        config.setdefault("logging", {})["level"] = level.upper()
    if path := os.getenv("LOG_FILE"):
        config.setdefault("logging", {})["file"] = path.strip()
    if origins := os.getenv("CORS_ORIGINS"):
        config.setdefault("security", {})["cors_origins"] = [o.strip() for o in origins.split(",")]
    if rate := os.getenv("RATE_LIMIT_PER_MINUTE"):
        try:
            config.setdefault("security", {})["rate_limit_requests_per_minute"] = int(rate)
        except ValueError:
            logger.warning("Invalid RATE_LIMIT_PER_MINUTE env value: %r, ignoring", rate)
    if model := os.getenv("EMBEDDINGS_MODEL"):
        config.setdefault("embeddings", {})["model"] = model
    if iterations := os.getenv("AGENT_MAX_ITERATIONS"):
        try:
            config.setdefault("agent", {})["max_iterations"] = int(iterations)
        except ValueError:
            logger.warning("Invalid AGENT_MAX_ITERATIONS env value: %r, ignoring", iterations)
    if url := os.getenv("SEARXNG_URL"):
        config.setdefault("web_search", {})["searxng_url"] = url.strip() or None
    if key := os.getenv("BRAVE_API_KEY"):
        config.setdefault("web_search", {})["brave_api_key"] = key.strip() or None
    if key := os.getenv("TAVILY_API_KEY"):
        config.setdefault("web_search", {})["tavily_api_key"] = key.strip() or None
    if key := os.getenv("GOOGLE_API_KEY"):
        config.setdefault("web_search", {})["google_api_key"] = key.strip() or None
    if cx := os.getenv("GOOGLE_CX"):
        config.setdefault("web_search", {})["google_cx"] = cx.strip() or None
    return config


def load_config(config_dir: Path | None = None) -> AppConfig:
    """Load configuration from TOML files with env overrides.

    Loads default.toml, then development.toml if exists.
    """
    if config_dir is None:
        config_dir = Path(__file__).resolve().parent.parent.parent.parent / "config"

    config: dict = {}

    default_path = config_dir / "default.toml"
    if default_path.exists():
        config = _load_toml(default_path)

    dev_path = config_dir / "development.toml"
    if dev_path.exists():
        dev_config = _load_toml(dev_path)
        for key, value in dev_config.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value

    config = _apply_env_overrides(config)

    server = ServerConfig(**(config.get("server") or {}))
    llm = LLMConfig(**(config.get("llm") or {}))
    ollama = OllamaConfig(**(config.get("ollama") or {}))
    openai_compat = OpenAICompatibleConfig(**(config.get("openai_compatible") or {}))
    models = _load_models_config(config.get("models") or {})
    embeddings = EmbeddingsConfig(**(config.get("embeddings") or {}))
    security = SecurityConfig(**(config.get("security") or {}))
    persistence = PersistenceConfig(**(config.get("persistence") or {}))
    rag = RAGConfig(**(config.get("rag") or {}))
    agent = AgentConfig(**(config.get("agent") or {}))
    web_search = WebSearchConfig(**(config.get("web_search") or {}))
    logging_raw = config.get("logging") or {}
    log_level = logging_raw.get("level", "INFO")
    log_file = (logging_raw.get("file") or "").strip()
    log_rotation_max_mb = int(logging_raw.get("log_rotation_max_mb", 5))
    log_rotation_backups = int(logging_raw.get("log_rotation_backups", 3))

    return AppConfig(
        server=server,
        llm=llm,
        ollama=ollama,
        openai_compatible=openai_compat,
        models=models,
        embeddings=embeddings,
        security=security,
        persistence=persistence,
        rag=rag,
        agent=agent,
        web_search=web_search,
        log_level=log_level,
        log_file=log_file,
        log_rotation_max_mb=log_rotation_max_mb,
        log_rotation_backups=log_rotation_backups,
    )
