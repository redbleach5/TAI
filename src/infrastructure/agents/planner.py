"""Planner agent - generates implementation plan from task."""

from collections.abc import Callable

from src.domain.entities.workflow_state import WorkflowState
from src.domain.ports.llm import LLMMessage, LLMPort
from src.infrastructure.agents.llm_helpers import stream_with_callback


async def planner_node(
    state: WorkflowState,
    llm: LLMPort,
    model: str,
    on_chunk: Callable[[str, str], None] | None = None,
) -> WorkflowState:
    """Generate implementation plan. Updates state['plan']."""
    task = state.get("task", "")
    messages = [
        LLMMessage(
            role="system",
            content="You are a coding assistant. Output only the plan, no code. Be concise.",
        ),
        LLMMessage(
            role="user",
            content=f"Task: {task}\n\nCreate a brief step-by-step implementation plan.",
        ),
    ]
    content = await stream_with_callback(
        llm=llm,
        messages=messages,
        model=model,
        event_type="plan",
        on_chunk=on_chunk,
    )
    return {**state, "plan": content, "current_step": "plan"}
