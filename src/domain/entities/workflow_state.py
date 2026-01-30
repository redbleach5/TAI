"""Workflow state schema for LangGraph."""

from typing import TypedDict


class WorkflowState(TypedDict, total=False):
    """State passed between workflow nodes. All fields optional for incremental build."""

    # Input
    task: str
    intent_kind: str  # "greeting" | "help" | "code" | "chat"
    template_response: str | None  # For greeting/help — skip workflow

    # Steps
    plan: str
    context: str  # From researcher (RAG in Phase 4)
    tests: str
    code: str
    validation_passed: bool
    validation_output: str
    error: str | None

    # Metadata
    current_step: str
    model: str
    messages: list  # History for LLM context
