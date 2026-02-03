"""Tests for TOML config loader."""

import os
import tempfile
from pathlib import Path

from src.infrastructure.config.toml_loader import _apply_env_overrides, load_config


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_default_config(self):
        """Loads default configuration."""
        config = load_config()

        # Should have all required sections
        assert config.server is not None
        assert config.llm is not None
        assert config.models is not None
        assert config.security is not None
        assert config.agent is not None
        assert config.agent.max_iterations == 15

    def test_loads_from_custom_dir(self):
        """Loads config from custom directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            default_toml = Path(tmpdir) / "default.toml"
            default_toml.write_text("""
[llm]
provider = "custom_provider"

[server]
port = 9999
""")
            config = load_config(Path(tmpdir))

            assert config.llm.provider == "custom_provider"
            assert config.server.port == 9999

    def test_merges_development_config(self):
        """Merges development.toml over default.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "default.toml").write_text("""
[llm]
provider = "ollama"

[server]
port = 8000
""")
            (Path(tmpdir) / "development.toml").write_text("""
[llm]
provider = "lm_studio"
""")
            config = load_config(Path(tmpdir))

            # Should be overridden
            assert config.llm.provider == "lm_studio"
            # Should be preserved from default
            assert config.server.port == 8000

    def test_handles_missing_files(self):
        """Handles missing config files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty directory - should use defaults
            config = load_config(Path(tmpdir))

            # Should have default values
            assert config.llm.provider == "ollama"


class TestApplyEnvOverrides:
    """Tests for _apply_env_overrides function."""

    def test_llm_provider_override(self):
        """LLM_PROVIDER env var overrides config."""
        config = {}
        os.environ["LLM_PROVIDER"] = "lm_studio"

        try:
            result = _apply_env_overrides(config)
            assert result["llm"]["provider"] == "lm_studio"
        finally:
            del os.environ["LLM_PROVIDER"]

    def test_ollama_host_override(self):
        """OLLAMA_HOST env var overrides config."""
        config = {}
        os.environ["OLLAMA_HOST"] = "http://custom:11434"

        try:
            result = _apply_env_overrides(config)
            assert result["ollama"]["host"] == "http://custom:11434"
        finally:
            del os.environ["OLLAMA_HOST"]

    def test_port_override(self):
        """PORT env var overrides config."""
        config = {}
        os.environ["PORT"] = "9000"

        try:
            result = _apply_env_overrides(config)
            assert result["server"]["port"] == 9000
        finally:
            del os.environ["PORT"]

    def test_invalid_port_ignored(self):
        """Invalid PORT value is ignored."""
        config = {"server": {"port": 8000}}
        os.environ["PORT"] = "not_a_number"

        try:
            result = _apply_env_overrides(config)
            assert result["server"]["port"] == 8000
        finally:
            del os.environ["PORT"]

    def test_log_level_override(self):
        """LOG_LEVEL env var overrides config."""
        config = {}
        os.environ["LOG_LEVEL"] = "debug"

        try:
            result = _apply_env_overrides(config)
            assert result["logging"]["level"] == "DEBUG"
        finally:
            del os.environ["LOG_LEVEL"]

    def test_cors_origins_override(self):
        """CORS_ORIGINS env var overrides config."""
        config = {}
        os.environ["CORS_ORIGINS"] = "http://a.com, http://b.com"

        try:
            result = _apply_env_overrides(config)
            assert result["security"]["cors_origins"] == ["http://a.com", "http://b.com"]
        finally:
            del os.environ["CORS_ORIGINS"]

    def test_rate_limit_override(self):
        """RATE_LIMIT_PER_MINUTE env var overrides config."""
        config = {}
        os.environ["RATE_LIMIT_PER_MINUTE"] = "200"

        try:
            result = _apply_env_overrides(config)
            assert result["security"]["rate_limit_requests_per_minute"] == 200
        finally:
            del os.environ["RATE_LIMIT_PER_MINUTE"]

    def test_embeddings_model_override(self):
        """EMBEDDINGS_MODEL env var overrides config."""
        config = {}
        os.environ["EMBEDDINGS_MODEL"] = "custom-embed"

        try:
            result = _apply_env_overrides(config)
            assert result["embeddings"]["model"] == "custom-embed"
        finally:
            del os.environ["EMBEDDINGS_MODEL"]

    def test_agent_max_iterations_override(self):
        """AGENT_MAX_ITERATIONS env var overrides config."""
        config = {}
        os.environ["AGENT_MAX_ITERATIONS"] = "20"
        try:
            result = _apply_env_overrides(config)
            assert result["agent"]["max_iterations"] == 20
        finally:
            del os.environ["AGENT_MAX_ITERATIONS"]
