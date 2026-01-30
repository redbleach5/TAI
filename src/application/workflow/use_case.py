"""Workflow use case - runs LangGraph workflow."""

import asyncio
import uuid
from collections.abc import AsyncIterator

from langgraph.checkpoint.memory import MemorySaver

from src.application.workflow.dto import (
    WorkflowRequest,
    WorkflowResponse,
    WorkflowStreamEvent,
)
from src.domain.entities.workflow_state import WorkflowState
from src.domain.ports.llm import LLMPort
from src.domain.ports.rag import RAGPort
from src.domain.services.model_router import ModelRouter
from src.infrastructure.workflow import build_workflow_graph, compile_workflow_graph


def _state_to_response(session_id: str, state: WorkflowState) -> WorkflowResponse:
    """Map workflow state to response."""
    template = state.get("template_response")
    if template:
        return WorkflowResponse(
            session_id=session_id,
            content=template,
            intent_kind=state.get("intent_kind", "chat"),
        )
    content = state.get("code", "") or state.get("plan", "") or ""
    return WorkflowResponse(
        session_id=session_id,
        content=content,
        intent_kind=state.get("intent_kind", "code"),
        plan=state.get("plan"),
        tests=state.get("tests"),
        code=state.get("code"),
        validation_passed=state.get("validation_passed"),
        validation_output=state.get("validation_output"),
        error=state.get("error"),
    )


class WorkflowUseCase:
    """Orchestrates workflow: intent → planner → researcher → tests → coder → validator."""

    def __init__(
        self,
        llm: LLMPort,
        model_router: ModelRouter,
        rag: RAGPort | None = None,
        checkpointer: MemorySaver | None = None,
    ) -> None:
        self._llm = llm
        self._model_router = model_router
        self._rag = rag
        self._checkpointer = checkpointer or MemorySaver()

    async def execute(self, request: WorkflowRequest) -> WorkflowResponse:
        """Run workflow synchronously, return full result."""
        session_id = request.session_id or str(uuid.uuid4())
        builder = build_workflow_graph(
            self._llm,
            self._model_router,
            on_chunk=None,
            rag=self._rag,
        )
        graph = compile_workflow_graph(builder, checkpointer=self._checkpointer)
        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}
        initial: WorkflowState = {
            "task": request.task,
            "messages": [],
        }
        final = await graph.ainvoke(initial, config=config)
        return _state_to_response(session_id, final)

    async def execute_stream(self, request: WorkflowRequest) -> AsyncIterator[WorkflowStreamEvent]:
        """Run workflow, stream events via SSE."""
        session_id = request.session_id or str(uuid.uuid4())
        queue: asyncio.Queue[WorkflowStreamEvent] = asyncio.Queue()

        def on_chunk(event_type: str, chunk: str) -> None:
            queue.put_nowait(WorkflowStreamEvent(event_type=event_type, chunk=chunk))

        builder = build_workflow_graph(
            self._llm,
            self._model_router,
            on_chunk=on_chunk,
            rag=self._rag,
        )
        graph = compile_workflow_graph(builder, checkpointer=self._checkpointer)
        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}
        initial: WorkflowState = {"task": request.task, "messages": []}

        async def run_graph() -> None:
            try:
                final = await graph.ainvoke(initial, config=config)
                queue.put_nowait(
                    WorkflowStreamEvent(
                        event_type="done",
                        payload={
                            "session_id": session_id,
                            "plan": final.get("plan"),
                            "tests": final.get("tests"),
                            "code": final.get("code"),
                            "validation_passed": final.get("validation_passed"),
                            "validation_output": final.get("validation_output"),
                            "template_response": final.get("template_response"),
                            "intent_kind": final.get("intent_kind"),
                        },
                    )
                )
            except Exception as e:
                queue.put_nowait(WorkflowStreamEvent(event_type="error", chunk=str(e)))

        task = asyncio.create_task(run_graph())
        try:
            while True:
                event = await queue.get()
                yield event
                if event.event_type == "done":
                    break
                if event.event_type == "error":
                    break
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
