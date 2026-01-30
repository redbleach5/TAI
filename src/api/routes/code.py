"""Code execution API - sandboxed code runner."""

import asyncio
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

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
            cmd = ["python", "-m", "pytest", "test_code.py", "-v", "--tb=short"]
        else:
            # Just run the code
            cmd = ["python", "code.py"]

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
async def run_code(request: CodeRunRequest) -> CodeRunResponse:
    """Execute Python code in a sandboxed subprocess."""
    if not request.code.strip():
        return CodeRunResponse(success=False, output="", error="Код пуст")

    # Run in thread to avoid blocking
    success, output, error = await asyncio.to_thread(
        _run_code_sync,
        request.code,
        request.tests,
        request.timeout,
    )

    return CodeRunResponse(success=success, output=output, error=error)
