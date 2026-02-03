"""Tests for model validator."""


import pytest
from unittest.mock import AsyncMock

from src.domain.ports.config import AppConfig, ModelConfig, LLMConfig
from src.infrastructure.config.model_validator import validate_models_config
from src.shared.logging import setup_logging


@pytest.fixture
def config():
    """App config with ollama models."""
    return AppConfig(
        llm=LLMConfig(provider="ollama"),
        models=ModelConfig(
            simple="qwen2.5-coder:7b",
            medium="glm-4.7-flash:latest",
            complex="gpt-oss:20b",
            fallback="qwen2.5-coder:7b",
        ),
    )


@pytest.mark.asyncio
async def test_validate_all_models_available(config):
    """When all configured models exist, no warning."""
    llm = AsyncMock()
    llm.list_models = AsyncMock(
        return_value=["qwen2.5-coder:7b", "glm-4.7-flash:latest", "gpt-oss:20b"]
    )
    await validate_models_config(llm, config)
    llm.list_models.assert_called_once()


@pytest.mark.asyncio
async def test_validate_missing_model_logs_warning(config, capsys):
    """When a configured model is missing, log warning to stdout."""
    setup_logging("INFO")
    llm = AsyncMock()
    llm.list_models = AsyncMock(return_value=["qwen2.5-coder:7b"])  # missing gpt-oss, glm

    await validate_models_config(llm, config)

    out, err = capsys.readouterr()
    out = out + err
    assert "configured_models_not_available" in out or "missing" in out.lower()


@pytest.mark.asyncio
async def test_validate_llm_unreachable_skips(config, capsys):
    """When LLM is unreachable, skip validation without failing."""
    setup_logging("INFO")
    llm = AsyncMock()
    llm.list_models = AsyncMock(side_effect=ConnectionError("Connection refused"))

    await validate_models_config(llm, config)

    out, err = capsys.readouterr()
    out = out + err
    assert "models_validation_skipped" in out or "llm_unreachable" in out.lower()


@pytest.mark.asyncio
async def test_validate_base_name_match(config):
    """Base name match: config 'gpt-oss' matches available 'gpt-oss:20b'."""
    config.models.complex = "gpt-oss"
    llm = AsyncMock()
    llm.list_models = AsyncMock(return_value=["gpt-oss:20b", "qwen2.5-coder:7b"])

    await validate_models_config(llm, config)

    llm.list_models.assert_called_once()
