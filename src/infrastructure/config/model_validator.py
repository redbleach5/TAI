"""Validate configured LLM models against available provider models at startup."""

import structlog

from src.domain.ports.config import AppConfig
from src.domain.ports.llm import LLMPort

log = structlog.get_logger()


async def validate_models_config(llm: LLMPort, config: AppConfig) -> None:
    """Check that configured models exist in the LLM provider. Log warnings for missing models.

    Does not fail startup if LLM is unreachable or models are missing.
    """
    provider = config.llm.provider
    models = config.models.get_models_for_provider(provider)

    try:
        available = await llm.list_models()
    except Exception as e:
        log.warning(
            "models_validation_skipped",
            reason="llm_unreachable",
            provider=provider,
            error=str(e),
        )
        return

    if not available:
        log.warning(
            "models_validation_skipped",
            reason="no_models_returned",
            provider=provider,
        )
        return

    # Normalize: exact names + base names (e.g. "gpt-oss" matches "gpt-oss:20b")
    available_set: set[str] = set()
    for m in available:
        if not m:
            continue
        name = m.strip().lower()
        available_set.add(name)
        if ":" in name:
            available_set.add(name.split(":")[0])

    configured = [
        ("simple", models.simple),
        ("medium", models.medium),
        ("complex", models.complex),
        ("fallback", models.fallback),
    ]

    missing: list[str] = []
    for role, model in configured:
        if not model:
            continue
        model_lower = model.strip().lower()
        base = model_lower.split(":")[0] if ":" in model_lower else model_lower
        if model_lower not in available_set and base not in available_set:
            missing.append(f"{role}={model}")

    if missing:
        hint = (
            "Pull with 'ollama pull <model>' or update config in development.toml"
            if provider == "ollama"
            else "Load model in LM Studio or update config in development.toml"
        )
        log.warning(
            "configured_models_not_available",
            provider=provider,
            missing=missing,
            available_count=len(available),
            hint=hint,
        )
    else:
        log.debug(
            "models_validation_ok",
            provider=provider,
            models=[m for _, m in configured if m],
        )
