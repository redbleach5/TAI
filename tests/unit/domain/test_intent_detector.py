"""IntentDetector unit tests."""

from src.domain.services.intent_detector import IntentDetector


def test_detect_greeting():
    """Greeting patterns return greeting intent with response."""
    detector = IntentDetector()
    for msg in ("hello", "hi", "привет", "Hey there"):
        intent = detector.detect(msg)
        assert intent.kind == "greeting"
        assert intent.response is not None
        assert "CodeGen" in intent.response or "привет" in intent.response.lower()


def test_detect_help():
    """Help patterns return help intent with response."""
    detector = IntentDetector()
    for msg in ("help", "помощь", "?"):
        intent = detector.detect(msg)
        assert intent.kind == "help"
        assert intent.response is not None


def test_detect_code():
    """Code patterns return code intent (no template, handled by workflow)."""
    detector = IntentDetector()
    for msg in ("write a function", "создай класс", "implement sorting"):
        intent = detector.detect(msg)
        assert intent.kind == "code"
        # Code intents don't have a template response - they're handled by workflow
        assert intent.response is None


def test_detect_chat():
    """Non-pattern messages return chat intent without template."""
    detector = IntentDetector()
    for msg in ("explain recursion", "what is a closure", "расскажи про декораторы"):
        intent = detector.detect(msg)
        assert intent.kind == "chat"
        assert intent.response is None


def test_detect_empty():
    """Empty message returns chat."""
    detector = IntentDetector()
    intent = detector.detect("   ")
    assert intent.kind == "chat"


def test_detect_greeting_case_insensitive():
    """Greeting detection is case-insensitive."""
    detector = IntentDetector()
    for msg in ("HELLO", "Hello", "ПРИВЕТ", "Привет"):
        intent = detector.detect(msg)
        assert intent.kind == "greeting"


def test_detect_greeting_with_extras():
    """Greeting patterns with extra text."""
    detector = IntentDetector()
    intent = detector.detect("hi there!")
    assert intent.kind == "greeting"


def test_detect_code_russian():
    """Russian code patterns."""
    detector = IntentDetector()
    for msg in ("напиши функцию", "реализуй алгоритм", "создай модуль"):
        intent = detector.detect(msg)
        assert intent.kind == "code"


def test_detect_code_english():
    """English code patterns."""
    detector = IntentDetector()
    for msg in ("write a function", "create a module", "implement auth"):
        intent = detector.detect(msg)
        assert intent.kind == "code"


def test_caching():
    """Same message returns cached result."""
    detector = IntentDetector()
    r1 = detector.detect("hello")
    r2 = detector.detect("hello")
    assert r1.kind == r2.kind
    assert r1.response == r2.response
