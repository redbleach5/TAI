"""Model Selector - auto-select by capability from available models (Ollama, LM Studio).

Uses config overrides when explicit models are set and available.
Otherwise picks by complexity: simple=smallest, medium=middle, complex=largest.
Caches available models for 60s to avoid hitting provider on every message.
"""

import time
from typing import TYPE_CHECKING

from src.domain.entities.model_selection import TaskComplexity
from src.domain.services.model_router import ModelRouter
from src.infrastructure.services.model_fetcher import fetch_models_with_capability

if TYPE_CHECKING:
    from src.domain.ports.config import AppConfig
    from src.domain.ports.llm import LLMPort


class ModelSelector:
    """Select model by complexity from available models. Config override when set."""

    CACHE_TTL = 60.0  # seconds

    def __init__(
        self,
        llm: "LLMPort",
        model_router: ModelRouter,
        config: "AppConfig",
    ) -> None:
        self._llm = llm
        self._model_router = model_router
        self._config = config
        self._provider = config.llm.provider
        self._ollama_host = config.ollama.host if config.llm.provider == "ollama" else None
        self._cache: list[tuple[str, float]] | None = None
        self._cache_time: float = 0.0

    async def _get_available(self) -> list[tuple[str, float]]:
        """Get available models with capability, use cache if fresh."""
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_time) < self.CACHE_TTL:
            return self._cache
        models = await fetch_models_with_capability(
            self._llm,
            self._provider,
            ollama_host=self._ollama_host,
        )
        self._cache = models
        self._cache_time = now
        return models

    def _configured_in_available(
        self,
        configured: str,
        available: list[tuple[str, float]],
    ) -> bool:
        """Check if configured model is in available list (exact or base name)."""
        if not configured:
            return False
        cfg = configured.strip().lower()
        cfg_base = cfg.split(":")[0] if ":" in cfg else cfg
        for name, _ in available:
            n = name.lower()
            n_base = n.split(":")[0] if ":" in n else n
            if cfg == n or cfg_base == n_base:
                return True
        return False

    async def select_model(self, message: str) -> tuple[str, str]:
        """Select (primary_model, fallback_model) by message complexity.

        Returns (model, fallback) for use in fallback chain.
        """
        complexity = self._model_router.detect_complexity(message)
        configured = self._model_router._models

        available = await self._get_available()
        names = [n for n, _ in available]

        if not names:
            # No available models - use config
            primary = self._model_router.select_model(message)
            return primary, configured.fallback

        # Check config override: use if set and available
        if complexity == TaskComplexity.SIMPLE and self._configured_in_available(
            configured.simple, available
        ):
            primary = configured.simple
        elif complexity == TaskComplexity.COMPLEX and self._configured_in_available(
            configured.complex, available
        ):
            primary = configured.complex
        elif complexity == TaskComplexity.MEDIUM and self._configured_in_available(
            configured.medium, available
        ):
            primary = configured.medium
        else:
            # Auto-select by capability: simple=smallest, complex=largest, medium=middle
            if complexity == TaskComplexity.SIMPLE:
                primary = names[0]
            elif complexity == TaskComplexity.COMPLEX:
                primary = names[-1]
            else:
                primary = names[len(names) // 2]

        # Fallback: config if available, else smallest
        if self._configured_in_available(configured.fallback, available):
            fallback = configured.fallback
        else:
            fallback = names[0]

        return primary, fallback

    @property
    def fallback_model(self) -> str:
        """Global fallback from config (used when cache empty)."""
        return self._model_router.fallback_model

    def clear_cache(self) -> None:
        """Clear available models cache (e.g. after pulling new model)."""
        self._cache = None
        self._cache_time = 0.0
