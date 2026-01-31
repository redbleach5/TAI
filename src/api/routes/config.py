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
    embeddings: dict | None = None
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
    return {
        "llm": {"provider": config.llm.provider},
        "models": {
            "defaults": defaults,
            "lm_studio": lm_studio,
        },
        "embeddings": {"model": config.embeddings.model},
        "logging": {"level": config.log_level},
    }


def _to_toml_structure(updates: dict) -> dict:
    """Convert frontend format to TOML structure."""
    result: dict = {}
    if "llm" in updates:
        result["llm"] = updates["llm"]
    if "embeddings" in updates:
        result["embeddings"] = updates["embeddings"]
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

    if "logging" in updates_dict and "level" in updates_dict.get("logging", {}):
        from src.shared.logging import setup_logging

        setup_logging(updates_dict["logging"]["level"])

    return {"ok": True, "message": "Config saved."}
