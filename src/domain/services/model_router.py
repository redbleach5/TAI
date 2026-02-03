"""Model Router - select model by task complexity with LRU cache."""

from functools import lru_cache

from src.domain.entities.model_selection import TaskComplexity
from src.domain.ports.config import ModelConfig

# Keywords that suggest complex tasks
COMPLEX_KEYWORDS = (
    "api",
    "rest",
    "full",
    "полноценн",
    "аутентификац",
    "authentication",
    "database",
    "база данных",
    "микросервис",
    "microservice",
    "архитектур",
    "architecture",
    "framework",
    "фреймворк",
    "интеграц",
    "integration",
    "рефакторинг",
    "refactor",
    "оптимиз",
    "optimize",
    "безопасност",
    "security",
    "тестирован",
    "testing",
)

# Keywords that suggest medium tasks
MEDIUM_KEYWORDS = (
    "функци",
    "function",
    "класс",
    "class",
    "модуль",
    "module",
    "алгоритм",
    "algorithm",
    "сортировк",
    "sort",
    "поиск",
    "search",
    "реализуй",
    "implement",
    "напиши код",
    "write code",
    "исправь",
    "fix",
    "добавь",
    "add",
)


class ModelRouter:
    """Select model by task complexity with LRU cache (128 entries).

    Uses config overrides per provider — no hardcoding.
    Caches complexity detection for repeated queries.
    """

    def __init__(
        self,
        config: ModelConfig,
        provider: str,
        cache_size: int = 128,
    ) -> None:
        self._config = config
        self._provider = provider
        self._models = config.get_models_for_provider(provider)

        # Create cached version of complexity detection
        self._cached_detect = lru_cache(maxsize=cache_size)(self._detect_impl)

    def _detect_impl(self, text: str) -> TaskComplexity:
        """Internal complexity detection (cached)."""
        if len(text) < 20:
            return TaskComplexity.SIMPLE

        # Check complex keywords first (higher priority)
        for kw in COMPLEX_KEYWORDS:
            if kw in text:
                return TaskComplexity.COMPLEX

        # Check medium keywords
        for kw in MEDIUM_KEYWORDS:
            if kw in text:
                return TaskComplexity.MEDIUM

        # Length-based heuristic
        if len(text) > 200:
            return TaskComplexity.COMPLEX
        if len(text) > 80:
            return TaskComplexity.MEDIUM

        return TaskComplexity.SIMPLE

    def detect_complexity(self, message: str) -> TaskComplexity:
        """Detect task complexity from message (cached)."""
        text = message.strip().lower()
        return self._cached_detect(text)

    def select_model(self, message: str) -> str:
        """Select model name by message complexity (cached)."""
        complexity = self.detect_complexity(message)
        if complexity == TaskComplexity.SIMPLE:
            return self._models.simple
        if complexity == TaskComplexity.COMPLEX:
            return self._models.complex
        return self._models.medium

    def get_fallback_chain(self, complexity: TaskComplexity) -> list[str]:
        """Get fallback models for given complexity. Try lighter models first."""
        if complexity == TaskComplexity.SIMPLE:
            return [self._models.simple]
        if complexity == TaskComplexity.COMPLEX:
            return [
                self._models.complex,
                self._models.medium,
                self._models.simple,
            ]
        return [self._models.medium, self._models.simple]

    @property
    def fallback_model(self) -> str:
        """Global fallback model when primary fails."""
        return self._models.fallback

    @property
    def fast_model(self) -> str:
        """Fast/light model for quick queries (Fast Advisor pattern)."""
        return self._models.simple

    def cache_info(self) -> dict:
        """Get cache statistics."""
        info = self._cached_detect.cache_info()
        return {
            "hits": info.hits,
            "misses": info.misses,
            "size": info.currsize,
            "maxsize": info.maxsize,
        }

    def clear_cache(self) -> None:
        """Clear the complexity cache."""
        self._cached_detect.cache_clear()
