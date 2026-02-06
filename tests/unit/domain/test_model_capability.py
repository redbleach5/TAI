"""Tests for model_capability — pure functions, zero mocks."""

import pytest

from src.domain.services.model_capability import (
    compute_capability,
    parse_capability_from_name,
    parse_capability_from_param_size,
)


class TestParseCapabilityFromParamSize:
    """parse_capability_from_param_size: Ollama-style param size strings."""

    @pytest.mark.parametrize(
        ("param_size", "expected"),
        [
            ("7B", 7.0),
            ("7b", 7.0),
            ("4.3B", 4.3),
            ("13B", 13.0),
            ("70b", 70.0),
            ("72B", 72.0),
            ("3.8B", 3.8),
            ("0.5B", 0.5),
        ],
    )
    def test_billions(self, param_size: str, expected: float):
        assert parse_capability_from_param_size(param_size) == expected

    @pytest.mark.parametrize(
        ("param_size", "expected"),
        [
            ("137M", 0.137),
            ("400M", 0.4),
            ("22M", 0.022),
        ],
    )
    def test_millions(self, param_size: str, expected: float):
        assert parse_capability_from_param_size(param_size) == pytest.approx(expected)

    @pytest.mark.parametrize("param_size", ["", "unknown", "abc", "  ", "0"])
    def test_invalid_returns_zero(self, param_size: str):
        assert parse_capability_from_param_size(param_size) == 0.0

    def test_none_returns_zero(self):
        assert parse_capability_from_param_size(None) == 0.0  # type: ignore[arg-type]

    def test_non_string_returns_zero(self):
        assert parse_capability_from_param_size(123) == 0.0  # type: ignore[arg-type]

    def test_whitespace_padding(self):
        assert parse_capability_from_param_size("  7B  ") == 7.0


class TestParseCapabilityFromName:
    """parse_capability_from_name: extract size from model name."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("qwen2.5-coder:7b", 7.0),
            ("llama3.2:3b", 3.0),
            ("mistral-7b", 7.0),
            ("gpt-oss:20b", 20.0),
            ("deepseek-coder-v2:33b", 33.0),
        ],
    )
    def test_parses_from_name(self, name: str, expected: float):
        assert parse_capability_from_name(name) == expected

    @pytest.mark.parametrize("name", ["phi-3-mini", "gpt-4o", "claude-3", "some-model"])
    def test_unknown_returns_default(self, name: str):
        assert parse_capability_from_name(name) == 5.0

    def test_empty_returns_default(self):
        assert parse_capability_from_name("") == 5.0

    def test_none_returns_default(self):
        assert parse_capability_from_name(None) == 5.0  # type: ignore[arg-type]


class TestComputeCapability:
    """compute_capability: prefer param_size, fallback to name."""

    def test_prefers_param_size(self):
        assert compute_capability("unknown-model", param_size="13B") == 13.0

    def test_falls_back_to_name(self):
        assert compute_capability("qwen2.5-coder:7b") == 7.0

    def test_falls_back_to_name_when_param_size_invalid(self):
        assert compute_capability("llama3:70b", param_size="unknown") == 70.0

    def test_no_info_returns_default(self):
        assert compute_capability("some-model") == 5.0

    def test_none_param_size(self):
        assert compute_capability("qwen:7b", param_size=None) == 7.0
