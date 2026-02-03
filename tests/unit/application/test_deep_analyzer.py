"""Tests for DeepAnalyzer."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.analysis.deep_analyzer import (
    DeepAnalyzer,
    _parse_step1_modules,
)


class TestParseStep1Modules:
    """Tests for _parse_step1_modules."""

    def test_valid_json(self):
        """Parse valid JSON response."""
        resp = '{"problematic_modules": ["src/main.py", "src/api/routes"]}'
        assert _parse_step1_modules(resp) == ["src/main.py", "src/api/routes"]

    def test_json_in_markdown_block(self):
        """Parse JSON from markdown code block."""
        resp = '```json\n{"problematic_modules": ["frontend/src/App.tsx"]}\n```'
        assert _parse_step1_modules(resp) == ["frontend/src/App.tsx"]

    def test_empty_response(self):
        """Empty response returns None."""
        assert _parse_step1_modules("") is None
        assert _parse_step1_modules("   ") is None

    def test_invalid_json(self):
        """Invalid JSON returns None."""
        assert _parse_step1_modules("not json") is None
        assert _parse_step1_modules('{"other": []}') is None

    def test_too_few_modules(self):
        """1 module is valid (min 1)."""
        resp = '{"problematic_modules": ["src/main.py"]}'
        assert _parse_step1_modules(resp) == ["src/main.py"]

    def test_max_modules(self):
        """5 modules is valid."""
        modules = ["a.py", "b.py", "c.py", "d.py", "e.py"]
        resp = json.dumps({"problematic_modules": modules})
        assert _parse_step1_modules(resp) == modules


class TestDeepAnalyzer:
    """Tests for DeepAnalyzer."""

    @pytest.fixture
    def project_dir(self):
        """Create minimal project for analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "src").mkdir(parents=True)
            (p / "src" / "main.py").write_text("print('hello')")
            (p / "pyproject.toml").write_text("[project]\nname = 'test'")
            yield tmpdir

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=MagicMock(content="# Резюме\nПроект в порядке."))
        return llm

    @pytest.fixture
    def mock_model_selector(self):
        selector = MagicMock()
        selector.select_model = AsyncMock(return_value=("llama2", "fallback"))
        return selector

    @pytest.mark.asyncio
    async def test_analyze_single_pass(self, project_dir, mock_llm, mock_model_selector):
        """Single-pass analysis (multi_step=False) returns LLM report."""
        analyzer = DeepAnalyzer(
            llm=mock_llm,
            model_selector=mock_model_selector,
            rag=None,
        )
        result = await analyzer.analyze(project_dir, multi_step=False)
        assert "Резюме" in result or "Проект" in result
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_invalid_path(self, mock_llm, mock_model_selector):
        """Invalid path raises ValueError."""
        analyzer = DeepAnalyzer(
            llm=mock_llm,
            model_selector=mock_model_selector,
            rag=None,
        )
        with pytest.raises(ValueError, match="Invalid project path"):
            await analyzer.analyze("/nonexistent/path/xyz")
