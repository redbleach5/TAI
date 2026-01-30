"""Intent detector - heuristic without LLM."""

from dataclasses import dataclass

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


@dataclass
class Intent:
    """Detected intent with optional template response."""

    kind: str  # "greeting" | "help" | "code" | "chat"
    response: str | None = None


class IntentDetector:
    """Fast heuristic intent detection."""

    def detect(self, message: str) -> Intent:
        """Detect intent from message. Returns template response for greeting/help."""
        text = message.strip().lower()
        if not text:
            return Intent(kind="chat")

        for pattern in GREETING_PATTERNS:
            if pattern in text or text.startswith(pattern):
                return Intent(
                    kind="greeting",
                    response=(
                        "Привет! Я CodeGen AI — локальный помощник для генерации кода. "
                        "Задай вопрос или опиши задачу."
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
                return Intent(
                    kind="code",
                    response=(
                        "Workflow для генерации кода будет в Phase 3. "
                        "Пока могу ответить как обычный чат — опиши задачу подробнее."
                    ),
                )

        return Intent(kind="chat")
