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
