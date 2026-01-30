"""Workflow API routes."""

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import get_workflow_use_case, limiter
from src.application.workflow.dto import WorkflowRequest
from src.application.workflow.use_case import WorkflowUseCase

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.post("")
@limiter.limit("30/minute")
async def workflow(
    request: Request,
    workflow_request: WorkflowRequest,
    use_case: WorkflowUseCase = Depends(get_workflow_use_case),
    stream: bool = False,
):
    """Run workflow. Use stream=true for SSE streaming."""
    if stream:
        return _stream_response(workflow_request, use_case)
    response = await use_case.execute(workflow_request)
    return response


def _stream_response(
    workflow_request: WorkflowRequest,
    use_case: WorkflowUseCase,
):
    """Return SSE stream of workflow events."""

    async def event_generator():
        async for evt in use_case.execute_stream(workflow_request):
            data = evt.model_dump_json()
            yield {"event": evt.event_type, "data": data}
        yield {"event": "close", "data": ""}

    return EventSourceResponse(event_generator())
