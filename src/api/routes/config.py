"""Config API - read and update settings (Phase 6)."""

import tomllib
from pathlib import Path

import tomli_w
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.container import reset_container
from src.api.dependencies import get_config
from src.domain.ports.config import AppConfig

router = APIRouter(prefix="/config", tags=["config"])


class ConfigPatch(BaseModel):
    """Partial config update. All fields optional."""

    llm: dict | None = None
    models: dict | None = None
    ollama: dict | None = None
    openai_compatible: dict | None = None
    embeddings: dict | None = None
    persistence: dict | None = None
    web_search: dict | None = None
    logging: dict | None = None


def _config_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "config"


def _development_path() -> Path:
    return _config_dir() / "development.toml"


@router.get("")
async def get_config_route(config: AppConfig = Depends(get_config)):
    """Return editable config subset for Settings UI."""
    models = config.models
    defaults = {
        "simple": models.simple,
        "medium": models.medium,
        "complex": models.complex,
        "fallback": models.fallback,
    }
    lm_studio = None
    if "lm_studio" in models.overrides:
        o = models.overrides["lm_studio"]
        lm_studio = {
            "simple": o.simple or defaults["simple"],
            "medium": o.medium or defaults["medium"],
            "complex": o.complex or defaults["complex"],
            "fallback": o.fallback or defaults["fallback"],
        }
    ollama: dict = {
        "host": config.ollama.host,
        "timeout": config.ollama.timeout,
    }
    if config.ollama.num_ctx is not None:
        ollama["num_ctx"] = config.ollama.num_ctx
    if config.ollama.num_predict is not None:
        ollama["num_predict"] = config.ollama.num_predict
    openai_compatible: dict = {
        "base_url": config.openai_compatible.base_url,
        "timeout": config.openai_compatible.timeout,
    }
    if config.openai_compatible.max_tokens is not None:
        openai_compatible["max_tokens"] = config.openai_compatible.max_tokens
    ws = config.web_search

    def _mask_key(value: str | None) -> str:
        if not value or not value.strip():
            return ""
        s = value.strip()
        return f"***{s[-4:]}" if len(s) >= 4 else "***"

    web_search = {
        "searxng_url": ws.searxng_url or "",
        "brave_api_key": _mask_key(ws.brave_api_key),
        "tavily_api_key": _mask_key(ws.tavily_api_key),
        "google_api_key": _mask_key(ws.google_api_key),
        "google_cx": ws.google_cx or "",
    }
    return {
        "llm": {"provider": config.llm.provider},
        "models": {
            "defaults": defaults,
            "lm_studio": lm_studio,
        },
        "ollama": ollama,
        "openai_compatible": openai_compatible,
        "embeddings": {"model": config.embeddings.model},
        "persistence": {"max_context_messages": config.persistence.max_context_messages},
        "web_search": web_search,
        "logging": {
            "level": config.log_level,
            "file": config.log_file or "",
            "log_rotation_max_mb": config.log_rotation_max_mb,
            "log_rotation_backups": config.log_rotation_backups,
        },
    }


def _to_toml_structure(updates: dict) -> dict:
    """Convert frontend format to TOML structure."""
    result: dict = {}
    if "llm" in updates:
        result["llm"] = updates["llm"]
    if "ollama" in updates:
        result["ollama"] = {k: v for k, v in updates["ollama"].items() if v is not None}
    if "openai_compatible" in updates:
        result["openai_compatible"] = {
            k: v for k, v in updates["openai_compatible"].items() if v is not None
        }
    if "embeddings" in updates:
        result["embeddings"] = updates["embeddings"]
    if "persistence" in updates:
        result["persistence"] = updates["persistence"]
    if "web_search" in updates:
        ws_keys = ("searxng_url", "brave_api_key", "tavily_api_key", "google_api_key", "google_cx")
        result["web_search"] = {
            k: v for k, v in updates["web_search"].items() if k in ws_keys
        }
    if "logging" in updates:
        result["logging"] = updates["logging"]
    if "models" in updates:
        m = updates["models"]
        models_section: dict = {}
        if "defaults" in m:
            models_section.update(m["defaults"])
        if "lm_studio" in m and m["lm_studio"] is not None:
            models_section["lm_studio"] = m["lm_studio"]
        if models_section:
            result["models"] = models_section
    return result


@router.patch("")
async def patch_config_route(updates: ConfigPatch):
    """Update development.toml with partial config. Changes apply immediately."""
    updates_dict = updates.model_dump(exclude_none=True)
    toml_updates = _to_toml_structure(updates_dict)
    if not toml_updates:
        return {"ok": True, "message": "No changes."}

    path = _development_path()
    existing: dict = {}
    if path.exists():
        with open(path, "rb") as f:
            existing = tomllib.load(f)

    def deep_merge(base: dict, patch: dict) -> dict:
        result = dict(base)
        for k, v in patch.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    merged = deep_merge(existing, toml_updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(merged, f)

    reset_container()

    if "logging" in updates_dict:
        from src.api.container import get_container
        from src.shared.logging import setup_logging

        c = get_container().config
        setup_logging(
            level=c.log_level,
            file_path=c.log_file or "",
            rotation_max_mb=c.log_rotation_max_mb,
            rotation_backups=c.log_rotation_backups,
        )

    return {"ok": True, "message": "Config saved."}
