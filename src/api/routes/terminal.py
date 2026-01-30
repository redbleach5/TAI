"""Terminal API routes - uses TerminalService."""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import limiter
from src.infrastructure.services.terminal_service import TerminalService

router = APIRouter(prefix="/terminal", tags=["terminal"])


class ExecRequest(BaseModel):
    """Execute command request."""
    command: str
    cwd: str | None = None


def _get_service() -> TerminalService:
    """Get TerminalService instance."""
    return TerminalService()


@router.post("/exec")
@limiter.limit("60/minute")
async def execute_command(request: Request, body: ExecRequest):
    """Execute a shell command.
    
    Only whitelisted commands are allowed.
    Dangerous patterns are blocked.
    """
    service = _get_service()
    result = await service.execute(body.command, body.cwd)
    
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
):
    """Stream command output via SSE."""
    service = _get_service()
    
    async def event_generator():
        async for line in service.stream(command, cwd):
            yield {"event": "output", "data": line}
        yield {"event": "done", "data": ""}
    
    return EventSourceResponse(event_generator())


@router.get("/commands")
@limiter.limit("60/minute")
async def list_commands(request: Request):
    """List allowed commands."""
    service = _get_service()
    return {"commands": service.list_allowed_commands()}
