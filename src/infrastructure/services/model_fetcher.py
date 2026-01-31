"""Fetch available models with capability scores for Ollama and LM Studio."""

from typing import TYPE_CHECKING

from src.domain.services.model_capability import compute_capability

if TYPE_CHECKING:
    from src.domain.ports.llm import LLMPort


async def fetch_models_with_capability(
    llm: "LLMPort",
    provider: str,
    ollama_host: str | None = None,
) -> list[tuple[str, float]]:
    """Fetch available models with capability scores.

    Ollama: uses /api/tags details.parameter_size when available.
    LM Studio: parses from model name (no param_size in API).
    Returns list of (model_name, capability_score) sorted by capability ascending.
    """
    if provider == "ollama" and ollama_host:
        return await _fetch_ollama_with_capability(ollama_host)
    return await _fetch_generic_with_capability(llm)


async def _fetch_ollama_with_capability(host: str) -> list[tuple[str, float]]:
    """Ollama: GET /api/tags, use details.parameter_size."""
    import httpx

    host = host.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{host}/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    models = data.get("models", [])
    result: list[tuple[str, float]] = []
    for m in models:
        name = m.get("name") or m.get("model") or ""
        if not name:
            continue
        # Skip embedding models (not for chat)
        if "embed" in name.lower():
            continue
        details = m.get("details") or {}
        param_size = details.get("parameter_size")
        cap = compute_capability(name, param_size)
        # Skip tiny models (< 0.5B) - likely embeddings or unusable for chat
        if cap > 0 and cap < 0.5:
            continue
        result.append((name, cap))

    # Sort by capability ascending (smallest first)
    result.sort(key=lambda x: x[1])
    return result


async def _fetch_generic_with_capability(llm: "LLMPort") -> list[tuple[str, float]]:
    """LM Studio / generic: list_models + parse from name."""
    try:
        names = await llm.list_models()
    except Exception:
        return []

    result: list[tuple[str, float]] = []
    for name in names:
        if not name:
            continue
        if "embed" in name.lower():
            continue
        cap = compute_capability(name, None)
        if cap > 0 and cap < 0.5:
            continue
        result.append((name, cap))

    result.sort(key=lambda x: x[1])
    return result
