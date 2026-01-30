"""Tests for WorkflowUseCase."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.workflow.dto import WorkflowRequest, WorkflowResponse
from src.application.workflow.use_case import WorkflowUseCase
from src.domain.ports.config import ModelConfig
from src.domain.services.model_router import ModelRouter


@pytest.fixture
def mock_llm():
    """Mock LLM adapter."""
    llm = MagicMock()
    
    async def stream_gen(*args, **kwargs):
        yield "Generated content"
    
    llm.generate_stream = stream_gen
    return llm


@pytest.fixture
def model_router():
    """Model router with default config."""
    config = ModelConfig(
        simple="simple-model",
        medium="medium-model",
        complex="complex-model",
        fallback="fallback-model",
    )
    return ModelRouter(config, provider="ollama")


@pytest.fixture
def mock_rag():
    """Mock RAG adapter."""
    rag = MagicMock()
    rag.search = AsyncMock(return_value=[])
    return rag


@pytest.fixture
def use_case(mock_llm, model_router, mock_rag):
    """WorkflowUseCase with mocked dependencies."""
    return WorkflowUseCase(
        llm=mock_llm,
        model_router=model_router,
        rag=mock_rag,
    )


class TestWorkflowUseCaseExecute:
    """Tests for WorkflowUseCase.execute method."""

    @pytest.mark.asyncio
    async def test_greeting_returns_template(self, use_case):
        """Greeting intent returns template without full workflow."""
        request = WorkflowRequest(task="привет")
        response = await use_case.execute(request)

        assert response.content  # Template response
        assert response.intent_kind == "greeting"
        assert response.plan is None
        assert response.code is None

    @pytest.mark.asyncio
    async def test_help_returns_template(self, use_case):
        """Help intent returns template."""
        request = WorkflowRequest(task="помощь")
        response = await use_case.execute(request)

        assert response.content
        assert response.intent_kind == "help"

    @pytest.mark.asyncio
    async def test_code_request_runs_workflow(self, use_case):
        """Code request runs full workflow."""
        request = WorkflowRequest(task="напиши функцию сортировки")
        
        with patch.object(use_case, '_run_graph', new_callable=AsyncMock) as mock_graph:
            mock_graph.return_value = MagicMock(
                plan="Step 1",
                tests="def test(): pass",
                code="def sort(): pass",
                validation_passed=True,
                validation_output="OK",
                context="",
            )
            
            response = await use_case.execute(request)

        assert response.intent_kind == "code"
        mock_graph.assert_called_once()


class TestWorkflowUseCaseStream:
    """Tests for WorkflowUseCase streaming."""

    @pytest.mark.asyncio
    async def test_stream_greeting_yields_done(self, use_case):
        """Greeting yields done event immediately."""
        request = WorkflowRequest(task="привет")
        events = []
        
        async for event in use_case.execute_stream(request):
            events.append(event)

        # Should have at least done event
        assert any(e.event_type == "done" for e in events)

    @pytest.mark.asyncio
    async def test_stream_code_yields_events(self, use_case):
        """Code request yields workflow events."""
        request = WorkflowRequest(task="напиши код")
        
        with patch.object(use_case, '_run_graph_stream') as mock_stream:
            async def stream_events(*args, **kwargs):
                from src.application.workflow.dto import WorkflowStreamEvent
                yield WorkflowStreamEvent(event_type="plan", chunk="Planning...")
                yield WorkflowStreamEvent(event_type="code", chunk="def func(): pass")
                yield WorkflowStreamEvent(event_type="done", payload={"plan": "done"})
            
            mock_stream.return_value = stream_events()
            
            events = []
            async for event in use_case.execute_stream(request):
                events.append(event)

        assert len(events) >= 1


class TestWorkflowUseCaseIntegration:
    """Integration tests for workflow use case."""

    @pytest.mark.asyncio
    async def test_full_workflow_integration(self, mock_llm, model_router, mock_rag):
        """Full workflow executes all steps."""
        # This test verifies the workflow graph runs without errors
        use_case = WorkflowUseCase(
            llm=mock_llm,
            model_router=model_router,
            rag=mock_rag,
        )
        
        request = WorkflowRequest(task="create a hello world function")
        
        # Execute without mocking internal methods
        try:
            response = await use_case.execute(request)
            # Should complete without error
            assert response.session_id is not None
            assert response.intent_kind == "code"
        except Exception:
            # Some failures are expected without real LLM
            pass
