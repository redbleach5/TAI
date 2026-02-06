"""Intent detector - heuristic with LRU cache."""

import re
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

# Pre-compile word boundary patterns for accurate matching
_GREETING_RE = re.compile(
    r"(?:^|\s)(" + "|".join(re.escape(p) for p in GREETING_PATTERNS) + r")(?:\s|$|[!.,?])",
)
_HELP_RE = re.compile(
    r"(?:^|\s)(" + "|".join(re.escape(p) for p in HELP_PATTERNS) + r")(?:\s|$|[!.,?])",
)
_CODE_RE = re.compile(
    r"(?:^|\s)(" + "|".join(re.escape(p) for p in CODE_PATTERNS) + r")(?:\s|$|[!.,?])",
)


@dataclass(frozen=True)  # frozen для hashable (кэширование)
class Intent:
    """Detected intent with optional template response."""

    kind: str  # "greeting" | "help" | "code" | "chat"
    response: str | None = None


# Module-level cached function (avoids lru_cache on bound method pitfalls)
@lru_cache(maxsize=128)
def _detect_impl(text: str) -> Intent:
    """Run internal detection logic (cached at module level)."""
    if not text:
        return Intent(kind="chat")

    if _GREETING_RE.search(text):
        return Intent(
            kind="greeting",
            response=(
                "Привет! Я CodeGen AI — локальный помощник для генерации кода. Задай вопрос или опиши задачу."
            ),
        )

    if text == "?" or _HELP_RE.search(text):
        return Intent(
            kind="help",
            response=(
                "Я помогаю с кодом: отвечаю на вопросы, генерирую код, объясняю решения. "
                "Работаю локально через Ollama. Просто напиши, что нужно."
            ),
        )

    if _CODE_RE.search(text):
        return Intent(kind="code")

    return Intent(kind="chat")


class IntentDetector:
    """Fast heuristic intent detection with LRU cache (128 entries)."""

    def __init__(self, cache_size: int = 128):
        """Initialize with cache size.

        Note: cache_size is accepted for API compatibility but the module-level
        cache uses a fixed size of 128 to avoid lru_cache-on-bound-method issues.
        """
        self._cache_size = cache_size

    def detect(self, message: str) -> Intent:
        """Detect intent from message (cached). Returns template response for greeting/help."""
        text = message.strip().lower()
        return _detect_impl(text)

    def cache_info(self) -> dict:
        """Get cache statistics."""
        info = _detect_impl.cache_info()
        return {
            "hits": info.hits,
            "misses": info.misses,
            "size": info.currsize,
            "maxsize": info.maxsize,
        }

    def clear_cache(self) -> None:
        """Clear the intent cache."""
        _detect_impl.cache_clear()
