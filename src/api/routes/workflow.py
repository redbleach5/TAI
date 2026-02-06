"""Workflow API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import get_workflow_use_case, limiter
from src.application.workflow.dto import WorkflowRequest
from src.application.workflow.use_case import WorkflowUseCase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.post("", response_model=None)
@limiter.limit("30/minute")
async def workflow(
    request: Request,
    workflow_request: WorkflowRequest,
    use_case: WorkflowUseCase = Depends(get_workflow_use_case),
    stream: bool = False,
) -> dict | EventSourceResponse:
    """Run workflow. Use stream=true for SSE streaming."""
    if stream:
        return _stream_response(workflow_request, use_case)
    try:
        return await use_case.execute(workflow_request)
    except Exception:
        logger.exception("Workflow execution failed")
        raise HTTPException(status_code=500, detail="Workflow execution failed")


def _stream_response(
    workflow_request: WorkflowRequest,
    use_case: WorkflowUseCase,
) -> EventSourceResponse:
    """Return SSE stream of workflow events."""

    async def event_generator():
        try:
            async for evt in use_case.execute_stream(workflow_request):
                data = evt.model_dump_json()
                yield {"event": evt.event_type, "data": data}
        except Exception:
            logger.exception("Workflow stream failed")
            yield {"event": "error", "data": "Stream failed"}
        yield {"event": "close", "data": ""}

    return EventSourceResponse(event_generator())
