"""Tests for Code Security Checker."""

from src.api.dependencies import get_security_checker
from src.infrastructure.services.code_security import (
    CodeSecurityChecker,
    SecurityCheckResult,
)


class TestCodeSecurityChecker:
    """Tests for CodeSecurityChecker."""

    def test_safe_code_passes(self):
        """Safe code should pass security check."""
        checker = CodeSecurityChecker()
        code = """
def hello(name: str) -> str:
    return f"Hello, {name}!"

print(hello("World"))
"""
        result = checker.check(code)
        assert result.is_safe is True
        assert len(result.blocked) == 0

    def test_dangerous_import_os(self):
        """Code with os import should trigger warning."""
        checker = CodeSecurityChecker()
        code = "import os\nos.listdir('.')"
        result = checker.check(code)
        assert any("import" in w.lower() and "os" in w.lower() for w in result.warnings)

    def test_dangerous_import_subprocess(self):
        """Code with subprocess import should trigger warning."""
        checker = CodeSecurityChecker()
        code = "import subprocess\nsubprocess.run(['ls'])"
        result = checker.check(code)
        has_w = any("subprocess" in w.lower() for w in result.warnings)
        has_b = any("subprocess" in b.lower() for b in result.blocked)
        assert has_w or has_b

    def test_dangerous_system_call_blocked(self):
        """Dangerous system calls should be blocked."""
        checker = CodeSecurityChecker()
        code = "import os\nos.system('rm -rf /')"
        result = checker.check(code)
        assert result.is_safe is False
        assert any("system" in b.lower() for b in result.blocked)

    def test_subprocess_run_blocked(self):
        """subprocess.run should be blocked."""
        checker = CodeSecurityChecker()
        code = "subprocess.run(['ls', '-la'])"
        result = checker.check(code)
        assert result.is_safe is False
        assert any("subprocess" in b.lower() for b in result.blocked)

    def test_eval_warning(self):
        """eval() should trigger warning."""
        checker = CodeSecurityChecker()
        code = "result = eval('2 + 2')"
        result = checker.check(code)
        assert any("eval" in w.lower() for w in result.warnings)

    def test_exec_warning(self):
        """exec() should trigger warning."""
        checker = CodeSecurityChecker()
        code = "exec('print(1)')"
        result = checker.check(code)
        assert any("exec" in w.lower() for w in result.warnings)

    def test_strict_mode_blocks_warnings(self):
        """In strict mode, warnings become blocking."""
        checker = CodeSecurityChecker(strict_mode=True)
        code = "import os"
        result = checker.check(code)
        assert result.is_safe is False

    def test_empty_code_is_safe(self):
        """Empty code should be safe."""
        checker = CodeSecurityChecker()
        result = checker.check("")
        assert result.is_safe is True
        assert len(result.warnings) == 0
        assert len(result.blocked) == 0

    def test_is_safe_for_execution(self):
        """is_safe_for_execution should be stricter."""
        checker = CodeSecurityChecker()
        # Code with warnings
        code = "import os\nprint('hello')"
        assert checker.is_safe_for_execution(code) is False

        # Safe code
        safe_code = "print('hello')"
        assert checker.is_safe_for_execution(safe_code) is True

    def test_sanitize_removes_dangerous_code(self):
        """sanitize() should remove dangerous lines."""
        checker = CodeSecurityChecker()
        code = """import os
import json
os.system('ls')
print('hello')
"""
        sanitized = checker.sanitize(code)
        assert "# REMOVED:" in sanitized
        assert "import json" in sanitized
        assert "print('hello')" in sanitized

    def test_get_security_checker_from_container(self):
        """get_security_checker (from dependencies) should return container instance."""
        checker = get_security_checker()
        assert isinstance(checker, CodeSecurityChecker)
        assert get_security_checker() is checker


class TestSecurityCheckResult:
    """Tests for SecurityCheckResult dataclass."""

    def test_result_creation(self):
        """SecurityCheckResult should be created correctly."""
        result = SecurityCheckResult(
            is_safe=True,
            warnings=["warning1"],
            blocked=[],
        )
        assert result.is_safe is True
        assert len(result.warnings) == 1
        assert len(result.blocked) == 0

    def test_result_with_blocked(self):
        """SecurityCheckResult with blocked items."""
        result = SecurityCheckResult(
            is_safe=False,
            warnings=[],
            blocked=["os.system detected"],
        )
        assert result.is_safe is False
        assert len(result.blocked) == 1
