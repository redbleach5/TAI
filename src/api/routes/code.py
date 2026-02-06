"""Code execution API - sandboxed code runner with security checks."""

import asyncio
import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_metrics, get_security_checker, limiter
from src.infrastructure.services.code_security import CodeSecurityChecker
from src.infrastructure.services.performance_metrics import PerformanceMetrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/code", tags=["code"])


class CodeRunRequest(BaseModel):
    """Request to run code."""

    code: str = Field(..., min_length=1, max_length=500_000)
    tests: str | None = Field(None, max_length=500_000)
    timeout: int = Field(30, ge=1, le=300)


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
            return False, "", f"Timeout: code execution exceeded {timeout} seconds"
        except Exception as e:
            logger.warning("Code execution error: %s", e)
            return False, "", str(e)


@router.post("/run")
@limiter.limit("30/minute")
async def run_code(
    request: Request,
    body: CodeRunRequest,
    checker: CodeSecurityChecker = Depends(get_security_checker),
    metrics: PerformanceMetrics = Depends(get_metrics),
) -> CodeRunResponse:
    """Execute Python code in a sandboxed subprocess.

    Security: Code is checked for dangerous operations before execution.
    """
    if not body.code.strip():
        return CodeRunResponse(success=False, output="", error="Empty code")

    # Security check
    security_result = checker.check(body.code)

    if not security_result.is_safe:
        blocked_str = "; ".join(security_result.blocked)
        return CodeRunResponse(
            success=False,
            output="",
            error=f"Security check failed: {blocked_str}",
        )

    # Run with metrics
    start = time.perf_counter()
    success, output, error = await asyncio.to_thread(
        _run_code_sync,
        body.code,
        body.tests,
        body.timeout,
    )
    metrics.record("code_execution", time.perf_counter() - start)

    # Add security warnings to output if any
    if security_result.warnings:
        warnings_str = "\n".join(f"Warning: {w}" for w in security_result.warnings)
        output = f"{warnings_str}\n\n{output}" if output else warnings_str

    return CodeRunResponse(success=success, output=output, error=error)


@router.post("/check")
@limiter.limit("60/minute")
async def check_code_security(
    request: Request,
    body: CodeRunRequest,
    checker: CodeSecurityChecker = Depends(get_security_checker),
) -> dict:
    """Check code for security issues without executing."""
    result = checker.check(body.code)

    return {
        "is_safe": result.is_safe,
        "warnings": result.warnings,
        "blocked": result.blocked,
    }


@router.get("/metrics")
@limiter.limit("60/minute")
async def get_code_metrics(
    request: Request,
    metrics: PerformanceMetrics = Depends(get_metrics),
) -> dict:
    """Get code execution performance metrics."""
    stats = metrics.get_stats("code_execution")
    return {"code_execution": stats}
