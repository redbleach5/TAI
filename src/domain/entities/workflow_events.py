"""Workflow event types for SSE streaming."""

from enum import Enum


class WorkflowEventType(str, Enum):
    """Event types streamed to client."""

    STEP = "step"  # current_step changed
    PLAN = "plan"
    TESTS = "tests"
    CODE = "code"
    VALIDATION = "validation"
    ERROR = "error"
    DONE = "done"
