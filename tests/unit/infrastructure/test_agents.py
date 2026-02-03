"""Tests for workflow agents."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agents.coder import coder_node
from src.infrastructure.agents.planner import planner_node
from src.infrastructure.agents.researcher import researcher_node
from src.infrastructure.agents.tests_writer import tests_writer_node as write_tests_node
from src.infrastructure.agents.validator import validator_node


@pytest.fixture
def mock_llm():
    """Mock LLM adapter with both generate and generate_stream."""
    llm = MagicMock()

    # Mock generate for non-streaming calls
    from src.domain.ports.llm import LLMResponse

    llm.generate = AsyncMock(
        return_value=LLMResponse(
            content="Step 1: Define function\nStep 2: Implement logic",
            model="test-model",
        )
    )

    # Mock generate_stream as async generator
    async def mock_stream(*args, **kwargs):
        yield "Step 1: Define function\n"
        yield "Step 2: Implement logic"

    llm.generate_stream = mock_stream

    return llm


@pytest.fixture
def base_state():
    """Base workflow state as dict (TypedDict)."""
    return {
        "task": "Write a factorial function",
        "intent_kind": "code",
        "current_step": "intent",
        "plan": "",
        "tests": "",
        "code": "",
        "context": "",
        "validation_passed": None,
        "validation_output": None,
    }


class TestPlanner:
    """Tests for planner agent."""

    @pytest.mark.asyncio
    async def test_planner_updates_state(self, mock_llm, base_state):
        """Planner updates state with plan."""

        async def mock_stream(*args, **kwargs):
            yield "Step 1: Define function\n"
            yield "Step 2: Implement logic"

        mock_llm.generate_stream = mock_stream

        result = await planner_node(base_state, mock_llm, "test-model", None)

        assert result["plan"] is not None
        assert "Step 1" in result["plan"]
        assert result["current_step"] == "plan"

    @pytest.mark.asyncio
    async def test_planner_calls_callback(self, mock_llm, base_state):
        """Planner calls on_chunk callback."""
        events = []

        def callback(event_type: str, text: str):
            events.append((event_type, text))

        async def mock_stream(*args, **kwargs):
            yield "Plan content"

        mock_llm.generate_stream = mock_stream

        await planner_node(base_state, mock_llm, "test-model", callback)

        assert len(events) > 0


class TestTestsWriter:
    """Tests for tests_writer agent."""

    @pytest.mark.asyncio
    async def test_tests_writer_updates_state(self, mock_llm, base_state):
        """Tests writer updates state with tests."""
        base_state["plan"] = "Step 1: Define function"

        # Mock generate for non-streaming case (on_chunk=None)
        from src.domain.ports.llm import LLMResponse

        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(
                content="def test_factorial():\n    assert factorial(5) == 120",
                model="test-model",
            )
        )

        result = await write_tests_node(base_state, mock_llm, "test-model", None)

        assert result["tests"] is not None
        assert "test_factorial" in result["tests"]
        assert result["current_step"] == "tests"


class TestCoder:
    """Tests for coder agent."""

    @pytest.mark.asyncio
    async def test_coder_updates_state(self, mock_llm, base_state):
        """Coder updates state with code."""
        base_state["plan"] = "Step 1: Define function"
        base_state["tests"] = "def test_factorial(): pass"

        # Mock generate for non-streaming case (on_chunk=None)
        from src.domain.ports.llm import LLMResponse

        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(
                content="def factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n-1)",
                model="test-model",
            )
        )

        result = await coder_node(base_state, mock_llm, "test-model", None)

        assert result["code"] is not None
        assert "factorial" in result["code"]
        assert result["current_step"] == "code"


class TestResearcher:
    """Tests for researcher agent."""

    @pytest.mark.asyncio
    async def test_researcher_with_rag(self, base_state):
        """Researcher uses RAG for context."""
        mock_rag = MagicMock()
        mock_rag.search = AsyncMock(
            return_value=[MagicMock(content="relevant code", metadata={"source": "test.py"}, score=0.9)]
        )

        base_state["plan"] = "Write factorial"

        result = await researcher_node(base_state, mock_rag)

        assert result["context"] is not None
        assert "relevant code" in result["context"]
        mock_rag.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_researcher_without_rag(self, base_state):
        """Researcher handles no RAG gracefully."""
        base_state["plan"] = "Write factorial"

        result = await researcher_node(base_state, None)

        assert result["context"] == ""


class TestValidator:
    """Tests for validator agent."""

    @pytest.mark.asyncio
    async def test_validator_with_code_and_tests(self, base_state):
        """Validator runs with code and tests."""
        base_state["code"] = "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)"
        base_state["tests"] = "def test_fact(): assert True"

        result = await validator_node(base_state)

        assert result["current_step"] == "validation"
        assert result["validation_output"] is not None

    @pytest.mark.asyncio
    async def test_validator_empty_code(self, base_state):
        """Validator handles empty code."""
        base_state["code"] = ""
        base_state["tests"] = ""

        result = await validator_node(base_state)

        assert result["validation_passed"] is False
        assert "No code or tests" in result["validation_output"]
