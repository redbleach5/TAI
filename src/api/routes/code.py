"""Code execution API - sandboxed code runner with security checks."""

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.dependencies import limiter
from src.infrastructure.services.code_security import get_security_checker
from src.infrastructure.services.performance_metrics import get_metrics

router = APIRouter(prefix="/code", tags=["code"])


class CodeRunRequest(BaseModel):
    """Request to run code."""

    code: str
    tests: str | None = None
    timeout: int = 30


class CodeRunResponse(BaseModel):
    """Response from code execution."""

    success: bool
    output: str
    error: str | None = None


def _run_code_sync(code: str, tests: str | None, timeout: int) -> tuple[bool, str, str | None]:
    """Run code in subprocess with timeout. Returns (success, output, error)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        code_file = path / "code.py"
        code_file.write_text(code, encoding="utf-8")

        # If tests provided, run pytest
        if tests and tests.strip():
            test_file = path / "test_code.py"
            # Ensure tests can import code
            test_content = "import sys\nsys.path.insert(0, '.')\nfrom code import *\n\n" + tests
            test_file.write_text(test_content, encoding="utf-8")
            cmd = [sys.executable, "-m", "pytest", "test_code.py", "-v", "--tb=short"]
        else:
            # Just run the code (use sys.executable for cross-platform)
            cmd = [sys.executable, "code.py"]

        try:
            result = subprocess.run(
                cmd,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout + result.stderr
            success = result.returncode == 0
            return success, output.strip(), None
        except subprocess.TimeoutExpired:
            return False, "", f"Timeout: код выполнялся дольше {timeout} секунд"
        except Exception as e:
            return False, "", str(e)


@router.post("/run")
@limiter.limit("30/minute")
async def run_code(request: Request, body: CodeRunRequest) -> CodeRunResponse:
    """Execute Python code in a sandboxed subprocess.
    
    Security: Code is checked for dangerous operations before execution.
    """
    if not body.code.strip():
        return CodeRunResponse(success=False, output="", error="Код пуст")
    
    # Security check
    checker = get_security_checker()
    security_result = checker.check(body.code)
    
    if not security_result.is_safe:
        blocked_str = "; ".join(security_result.blocked)
        return CodeRunResponse(
            success=False,
            output="",
            error=f"Security check failed: {blocked_str}",
        )
    
    # Run with metrics
    metrics = get_metrics()
    import time
    start = time.perf_counter()
    
    # Run in thread to avoid blocking
    success, output, error = await asyncio.to_thread(
        _run_code_sync,
        body.code,
        body.tests,
        body.timeout,
    )
    
    metrics.record("code_execution", time.perf_counter() - start)
    
    # Add security warnings to output if any
    if security_result.warnings:
        warnings_str = "\n".join(f"⚠️ {w}" for w in security_result.warnings)
        output = f"{warnings_str}\n\n{output}" if output else warnings_str

    return CodeRunResponse(success=success, output=output, error=error)


@router.post("/check")
@limiter.limit("60/minute")
async def check_code_security(request: Request, body: CodeRunRequest):
    """Check code for security issues without executing."""
    checker = get_security_checker()
    result = checker.check(body.code)
    
    return {
        "is_safe": result.is_safe,
        "warnings": result.warnings,
        "blocked": result.blocked,
    }


@router.get("/metrics")
@limiter.limit("60/minute")
async def get_code_metrics(request: Request):
    """Get code execution performance metrics."""
    metrics = get_metrics()
    stats = metrics.get_stats("code_execution")
    return {"code_execution": stats}
