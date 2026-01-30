"""Tests writer agent - generates pytest tests from plan and task."""

from collections.abc import Callable

from src.domain.entities.workflow_state import WorkflowState
from src.domain.ports.llm import LLMMessage, LLMPort
from src.infrastructure.agents.llm_helpers import stream_with_callback


async def tests_writer_node(
    state: WorkflowState,
    llm: LLMPort,
    model: str,
    on_chunk: Callable[[str, str], None] | None = None,
) -> WorkflowState:
    """Generate pytest tests. Updates state['tests']."""
    task = state.get("task", "")
    plan = state.get("plan", "")
    context = state.get("context", "")
    user_content = f"Task: {task}\n\nPlan: {plan}\n\n"
    if context:
        user_content += f"Relevant code from project:\n{context}\n\n"
    user_content += "Write pytest tests for the implementation."
    messages = [
        LLMMessage(
            role="system",
            content="You are a coding assistant. Output only Python pytest code. No explanations.",
        ),
        LLMMessage(role="user", content=user_content),
    ]
    content = await stream_with_callback(
        llm=llm,
        messages=messages,
        model=model,
        event_type="tests",
        on_chunk=on_chunk,
    )
    return {**state, "tests": content, "current_step": "tests"}
