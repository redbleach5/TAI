"""Model Router - select model by task complexity. Provider-agnostic: uses config overrides."""

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
)


class ModelRouter:
    """Select model by task complexity. Uses config overrides per provider — no hardcoding."""

    def __init__(self, config: ModelConfig, provider: str) -> None:
        self._config = config
        self._provider = provider
        self._models = config.get_models_for_provider(provider)

    def detect_complexity(self, message: str) -> TaskComplexity:
        """Detect task complexity from message. Heuristic only."""
        text = message.strip().lower()
        if len(text) < 20:
            return TaskComplexity.SIMPLE
        for kw in COMPLEX_KEYWORDS:
            if kw in text:
                return TaskComplexity.COMPLEX
        for kw in MEDIUM_KEYWORDS:
            if kw in text:
                return TaskComplexity.MEDIUM
        if len(text) > 150:
            return TaskComplexity.COMPLEX
        if len(text) > 60:
            return TaskComplexity.MEDIUM
        return TaskComplexity.SIMPLE

    def select_model(self, message: str) -> str:
        """Select model name by message complexity. Uses provider-specific models from config."""
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
