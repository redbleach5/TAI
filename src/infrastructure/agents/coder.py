"""Coder agent - generates implementation code from plan and tests."""

from collections.abc import Callable

from src.domain.entities.workflow_state import WorkflowState
from src.domain.ports.llm import LLMMessage, LLMPort
from src.infrastructure.agents.llm_helpers import stream_with_callback


async def coder_node(
    state: WorkflowState,
    llm: LLMPort,
    model: str,
    on_chunk: Callable[[str, str], None] | None = None,
) -> WorkflowState:
    """Generate implementation code. Updates state['code']."""
    task = state.get("task", "")
    plan = state.get("plan", "")
    tests = state.get("tests", "")
    context = state.get("context", "")
    user_content = f"Task: {task}\n\nPlan: {plan}\n\nTests to pass:\n{tests}\n\n"
    if context:
        user_content += f"Relevant code from project:\n{context}\n\n"
    user_content += "Write the implementation."
    messages = [
        LLMMessage(
            role="system",
            content=(
                "You are a coding assistant. Output only Python code. No markdown, no explanations."
            ),
        ),
        LLMMessage(role="user", content=user_content),
    ]
    content = await stream_with_callback(
        llm=llm,
        messages=messages,
        model=model,
        event_type="code",
        on_chunk=on_chunk,
    )
    return {**state, "code": content, "current_step": "code"}
