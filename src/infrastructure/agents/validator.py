"""Validator agent - runs tests via subprocess with timeout."""

import asyncio
import tempfile
from pathlib import Path

from src.domain.entities.workflow_state import WorkflowState


def _run_pytest_sync(tmpdir: str, code: str, tests: str) -> tuple[bool, str]:
    """Run pytest in subprocess. Returns (passed, output)."""
    import subprocess

    path = Path(tmpdir)
    (path / "impl.py").write_text(code, encoding="utf-8")
    test_content = tests
    if "from impl" not in test_content and "import impl" not in test_content:
        test_content = "import sys\nsys.path.insert(0, '.')\n" + test_content
    (path / "test_impl.py").write_text(test_content, encoding="utf-8")
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "test_impl.py", "-v", "--tb=short"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Validation timeout (30s)"
    except Exception as e:
        return False, str(e)


async def validator_node(state: WorkflowState) -> WorkflowState:
    """Validate code by running pytest. Uses asyncio.to_thread to avoid blocking."""
    code = state.get("code", "")
    tests = state.get("tests", "")
    if not code or not tests:
        return {
            **state,
            "validation_passed": False,
            "validation_output": "No code or tests",
            "current_step": "validation",
        }

    with tempfile.TemporaryDirectory() as tmpdir:
        passed, output = await asyncio.to_thread(_run_pytest_sync, tmpdir, code, tests)

    return {
        **state,
        "validation_passed": passed,
        "validation_output": output,
        "current_step": "validation",
    }
