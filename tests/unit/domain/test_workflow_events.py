"""Tests for workflow event types."""

from src.domain.entities.workflow_events import WorkflowEventType


def test_event_types_are_strings():
    """All event types should be string enums."""
    assert WorkflowEventType.STEP == "step"
    assert WorkflowEventType.PLAN == "plan"
    assert WorkflowEventType.TESTS == "tests"
    assert WorkflowEventType.CODE == "code"
    assert WorkflowEventType.VALIDATION == "validation"
    assert WorkflowEventType.ERROR == "error"
    assert WorkflowEventType.DONE == "done"


def test_event_type_value_access():
    """Can access event type as string."""
    assert WorkflowEventType.PLAN.value == "plan"
    assert WorkflowEventType.CODE.value == "code"


def test_all_event_types_defined():
    """All expected event types exist."""
    expected = {"step", "plan", "tests", "code", "validation", "error", "done"}
    actual = {e.value for e in WorkflowEventType}
    assert actual == expected
