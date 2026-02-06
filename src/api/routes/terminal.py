"""Terminal API routes - uses TerminalService."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import get_terminal_service, limiter
from src.infrastructure.services.terminal_service import TerminalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/terminal", tags=["terminal"])


class ExecRequest(BaseModel):
    """Execute command request."""

    command: str = Field(..., min_length=1, max_length=10_000)
    cwd: str | None = Field(None, max_length=1024)


@router.post("/exec")
@limiter.limit("60/minute")
async def execute_command(
    request: Request,
    body: ExecRequest,
    service: TerminalService = Depends(get_terminal_service),
) -> dict:
    """Execute a shell command.

    Only whitelisted commands are allowed.
    Dangerous patterns are blocked.
    """
    try:
        result = await service.execute(body.command, body.cwd)
    except Exception:
        logger.exception("Failed to execute command: %s", body.command)
        raise HTTPException(status_code=500, detail="Failed to execute command")

    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "error": result.error,
    }


@router.get("/stream")
@limiter.limit("30/minute")
async def stream_command(
    request: Request,
    command: str,
    cwd: str | None = None,
    service: TerminalService = Depends(get_terminal_service),
) -> EventSourceResponse:
    """Stream command output via SSE."""

    async def event_generator():
        try:
            async for line in service.stream(command, cwd):
                yield {"event": "output", "data": line}
        except Exception:
            logger.exception("Error streaming command: %s", command)
            yield {"event": "error", "data": "Stream failed"}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


@router.get("/commands")
@limiter.limit("60/minute")
async def list_commands(
    request: Request,
    service: TerminalService = Depends(get_terminal_service),
) -> dict:
    """List allowed commands."""
    return {"commands": service.list_allowed_commands()}
