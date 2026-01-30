"""ModelRouter unit tests."""
from src.domain.ports.config import ModelConfig, ProviderModelSet
from src.domain.services.model_router import ModelRouter


def test_select_model_simple():
    """Short message uses simple model."""
    config = ModelConfig(simple="phi3:mini", medium="qwen:7b", complex="qwen:32b")
    router = ModelRouter(config, provider="ollama")
    model = router.select_model("hi")
    assert model == "phi3:mini"


def test_select_model_medium():
    """Medium keywords use medium model."""
    config = ModelConfig(simple="phi3:mini", medium="qwen:7b", complex="qwen:32b")
    router = ModelRouter(config, provider="ollama")
    model = router.select_model("напиши функцию сортировки")
    assert model == "qwen:7b"


def test_select_model_complex():
    """Complex keywords use complex model."""
    config = ModelConfig(simple="phi3:mini", medium="qwen:7b", complex="qwen:32b")
    router = ModelRouter(config, provider="ollama")
    model = router.select_model("создай полноценный REST API с аутентификацией")
    assert model == "qwen:32b"


def test_fallback_model():
    """Fallback model is configurable."""
    config = ModelConfig(fallback="phi3:mini")
    router = ModelRouter(config, provider="ollama")
    assert router.fallback_model == "phi3:mini"


def test_provider_overrides_use_override_models():
    """Provider overrides use config overrides, not defaults."""
    config = ModelConfig(
        simple="phi3:mini",
        medium="qwen:7b",
        complex="qwen:32b",
        fallback="phi3:mini",
        overrides={
            "lm_studio": ProviderModelSet(
                simple="local",
                medium="local",
                complex="local",
                fallback="local",
            ),
        },
    )
    router = ModelRouter(config, provider="lm_studio")
    assert router.select_model("hi") == "local"
    assert router.select_model("напиши функцию") == "local"
    assert router.fallback_model == "local"


def test_provider_without_override_uses_defaults():
    """Unknown provider uses default models."""
    config = ModelConfig(simple="phi3:mini", medium="qwen:7b", complex="qwen:32b")
    router = ModelRouter(config, provider="openai")
    assert router.select_model("hi") == "phi3:mini"
