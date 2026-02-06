"""ModelRouter unit tests."""

from src.domain.entities.model_selection import TaskComplexity
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


def test_get_fallback_chain_simple():
    """Simple complexity returns only simple model."""
    config = ModelConfig(simple="s", medium="m", complex="c")
    router = ModelRouter(config, provider="ollama")
    chain = router.get_fallback_chain(TaskComplexity.SIMPLE)
    assert chain == ["s"]


def test_get_fallback_chain_medium():
    """Medium complexity returns medium then simple."""
    config = ModelConfig(simple="s", medium="m", complex="c")
    router = ModelRouter(config, provider="ollama")
    chain = router.get_fallback_chain(TaskComplexity.MEDIUM)
    assert chain == ["m", "s"]


def test_get_fallback_chain_complex():
    """Complex complexity returns complex, medium, simple."""
    config = ModelConfig(simple="s", medium="m", complex="c")
    router = ModelRouter(config, provider="ollama")
    chain = router.get_fallback_chain(TaskComplexity.COMPLEX)
    assert chain == ["c", "m", "s"]


def test_detect_complexity_caching():
    """Same message should use cache."""
    config = ModelConfig(simple="s", medium="m", complex="c")
    router = ModelRouter(config, provider="ollama")
    router.select_model("hello")
    router.select_model("hello")
    info = router.cache_info()
    assert info["hits"] >= 1


def test_fast_model():
    """fast_model returns simple model."""
    config = ModelConfig(simple="phi3:mini", medium="qwen:7b", complex="qwen:32b")
    router = ModelRouter(config, provider="ollama")
    assert router.fast_model == "phi3:mini"


def test_clear_cache():
    """clear_cache resets hit counter."""
    config = ModelConfig(simple="s", medium="m", complex="c")
    router = ModelRouter(config, provider="ollama")
    router.select_model("hi")
    router.clear_cache()
    info = router.cache_info()
    assert info["size"] == 0


def test_length_based_medium():
    """Message > 80 chars without keywords uses medium model."""
    config = ModelConfig(simple="s", medium="m", complex="c")
    router = ModelRouter(config, provider="ollama")
    # Long message without any keywords
    msg = "a " * 50  # 100 chars
    assert router.detect_complexity(msg) == TaskComplexity.MEDIUM


def test_length_based_complex():
    """Message > 200 chars without keywords uses complex model."""
    config = ModelConfig(simple="s", medium="m", complex="c")
    router = ModelRouter(config, provider="ollama")
    msg = "a " * 120  # 240 chars
    assert router.detect_complexity(msg) == TaskComplexity.COMPLEX
