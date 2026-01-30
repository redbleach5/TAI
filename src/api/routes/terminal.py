"""Terminal API - execute commands with streaming output."""

import asyncio
import os
import shlex
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.dependencies import limiter

router = APIRouter(prefix="/terminal", tags=["terminal"])

# Allowed commands whitelist for security
ALLOWED_COMMANDS = {
    # Python
    "python", "python3", "pip", "pytest", "ruff",
    # Node
    "node", "npm", "npx",
    # Git (read-only mostly handled by git API)
    "git",
    # System tools
    "ls", "cat", "head", "tail", "grep", "find", "wc",
    "echo", "pwd", "cd", "mkdir", "rm", "cp", "mv", "touch",
    # Build tools
    "make", "cargo", "go",
}

# Max execution time in seconds
MAX_TIMEOUT = 60


class ExecRequest(BaseModel):
    """Request to execute command."""
    command: str
    cwd: str | None = None
    timeout: int = 30


class ExecResponse(BaseModel):
    """Response from command execution."""
    success: bool
    command: str
    stdout: str
    stderr: str
    exit_code: int | None = None
    error: str | None = None


def _validate_command(command: str) -> tuple[bool, str]:
    """Validate command against whitelist.
    
    Returns:
        (is_valid, error_message)
    """
    try:
        parts = shlex.split(command)
        if not parts:
            return False, "Empty command"
        
        base_cmd = os.path.basename(parts[0])
        if base_cmd not in ALLOWED_COMMANDS:
            return False, f"Command not allowed: {base_cmd}"
        
        # Block dangerous patterns
        dangerous = ["&&", "||", ";", "|", ">", "<", "`", "$", "eval", "exec"]
        for d in dangerous:
            if d in command:
                return False, f"Dangerous pattern not allowed: {d}"
        
        return True, ""
    except ValueError as e:
        return False, f"Invalid command syntax: {e}"


async def _run_command(
    command: str,
    cwd: str | None = None,
    timeout: int = 30,
) -> dict:
    """Run command and return result."""
    # Validate
    is_valid, error = _validate_command(command)
    if not is_valid:
        return {
            "success": False,
            "command": command,
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "error": error,
        }
    
    # Resolve working directory
    work_dir = cwd if cwd else os.getcwd()
    if not os.path.isabs(work_dir):
        work_dir = os.path.join(os.getcwd(), work_dir)
    
    # Security: check cwd is within project
    try:
        os.path.relpath(work_dir, os.getcwd())
    except ValueError:
        return {
            "success": False,
            "command": command,
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "error": f"Security: cannot execute in directory outside project: {work_dir}",
        }
    
    try:
        # Clamp timeout
        timeout = min(timeout, MAX_TIMEOUT)
        
        # Run command
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
            
            return {
                "success": process.returncode == 0,
                "command": command,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": process.returncode,
                "error": None,
            }
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "success": False,
                "command": command,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"Command timed out after {timeout}s",
            }
    except Exception as e:
        return {
            "success": False,
            "command": command,
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "error": str(e),
        }


async def _stream_command(
    command: str,
    cwd: str | None = None,
    timeout: int = 30,
) -> AsyncIterator[str]:
    """Stream command output as SSE events."""
    import json
    
    # Validate
    is_valid, error = _validate_command(command)
    if not is_valid:
        yield f"data: {json.dumps({'type': 'error', 'data': error})}\n\n"
        return
    
    # Resolve working directory
    work_dir = cwd if cwd else os.getcwd()
    if not os.path.isabs(work_dir):
        work_dir = os.path.join(os.getcwd(), work_dir)
    
    try:
        timeout = min(timeout, MAX_TIMEOUT)
        
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )
        
        yield f"data: {json.dumps({'type': 'start', 'command': command, 'pid': process.pid})}\n\n"
        
        async def read_stream(stream, stream_type: str):
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace")
                yield f"data: {json.dumps({'type': stream_type, 'data': text})}\n\n"
        
        # Read both stdout and stderr
        stdout_task = asyncio.create_task(
            asyncio.wait_for(process.stdout.read(), timeout=timeout)
        )
        stderr_task = asyncio.create_task(
            asyncio.wait_for(process.stderr.read(), timeout=timeout)
        )
        
        try:
            stdout, stderr = await asyncio.gather(stdout_task, stderr_task)
            
            if stdout:
                yield f"data: {json.dumps({'type': 'stdout', 'data': stdout.decode('utf-8', errors='replace')})}\n\n"
            if stderr:
                yield f"data: {json.dumps({'type': 'stderr', 'data': stderr.decode('utf-8', errors='replace')})}\n\n"
            
            await process.wait()
            yield f"data: {json.dumps({'type': 'exit', 'exit_code': process.returncode})}\n\n"
            
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            yield f"data: {json.dumps({'type': 'error', 'data': f'Timeout after {timeout}s'})}\n\n"
            
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"


@router.post("/exec")
@limiter.limit("30/minute")
async def exec_command(
    request: Request,
    body: ExecRequest,
) -> ExecResponse:
    """Execute a command and return result.
    
    Security: Commands are validated against whitelist.
    Dangerous patterns (&&, ||, ;, |, >, <) are blocked.
    """
    result = await _run_command(body.command, body.cwd, body.timeout)
    return ExecResponse(**result)


@router.get("/stream")
@limiter.limit("10/minute")
async def stream_command(
    request: Request,
    command: str,
    cwd: str | None = None,
    timeout: int = 30,
):
    """Stream command output as SSE.
    
    Events:
    - start: {command, pid}
    - stdout: {data}
    - stderr: {data}
    - exit: {exit_code}
    - error: {data}
    """
    return StreamingResponse(
        _stream_command(command, cwd, timeout),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
