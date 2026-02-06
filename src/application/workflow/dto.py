"""Workflow DTOs."""

from pydantic import BaseModel, Field


class WorkflowRequest(BaseModel):
    """Request to run workflow."""

    task: str = Field(..., min_length=1, max_length=50_000)
    session_id: str | None = Field(None, max_length=100)  # For checkpointing; auto-generated if omitted


class WorkflowResponse(BaseModel):
    """Response from workflow execution."""

    session_id: str
    content: str  # Template response (greeting/help) or final code/plan summary
    intent_kind: str
    plan: str | None = None
    tests: str | None = None
    code: str | None = None
    validation_passed: bool | None = None
    validation_output: str | None = None
    error: str | None = None


class WorkflowStreamEvent(BaseModel):
    """SSE event for streaming workflow progress."""

    event_type: str  # plan, tests, code, validation, step, error, done
    chunk: str | None = None  # Incremental content
    payload: dict | None = None  # Full state on done
