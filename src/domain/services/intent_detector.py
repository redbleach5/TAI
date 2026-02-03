"""Intent detector - heuristic with LRU cache."""

from dataclasses import dataclass
from functools import lru_cache

GREETING_PATTERNS = ("привет", "hello", "hi", "hey", "здравствуй", "добрый день")
HELP_PATTERNS = ("помощь", "help", "?", "что умеешь", "как пользоваться")
CODE_PATTERNS = (
    "напиши",
    "создай",
    "реализуй",
    "исправ",
    "сделай",
    "добавь",
    "напиши код",
    "write",
    "create",
    "implement",
    "fix",
    "add",
    "generate code",
    "make a",
)


@dataclass(frozen=True)  # frozen для hashable (кэширование)
class Intent:
    """Detected intent with optional template response."""

    kind: str  # "greeting" | "help" | "code" | "chat"
    response: str | None = None


class IntentDetector:
    """Fast heuristic intent detection with LRU cache (128 entries)."""

    def __init__(self, cache_size: int = 128):
        """Initialize with cache size."""
        # Создаем кэшированную версию _detect
        self._cached_detect = lru_cache(maxsize=cache_size)(self._detect_impl)

    def _detect_impl(self, text: str) -> Intent:
        """Internal detection logic (cached)."""
        if not text:
            return Intent(kind="chat")

        for pattern in GREETING_PATTERNS:
            if pattern in text or text.startswith(pattern):
                return Intent(
                    kind="greeting",
                    response=(
                        "Привет! Я CodeGen AI — локальный помощник для генерации кода. Задай вопрос или опиши задачу."
                    ),
                )

        for pattern in HELP_PATTERNS:
            if pattern in text or text == "?":
                return Intent(
                    kind="help",
                    response=(
                        "Я помогаю с кодом: отвечаю на вопросы, генерирую код, объясняю решения. "
                        "Работаю локально через Ollama. Просто напиши, что нужно."
                    ),
                )

        for pattern in CODE_PATTERNS:
            if pattern in text:
                return Intent(kind="code")  # Больше не возвращаем placeholder

        return Intent(kind="chat")

    def detect(self, message: str) -> Intent:
        """Detect intent from message (cached). Returns template response for greeting/help."""
        text = message.strip().lower()
        return self._cached_detect(text)

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
        """Clear the intent cache."""
        self._cached_detect.cache_clear()
