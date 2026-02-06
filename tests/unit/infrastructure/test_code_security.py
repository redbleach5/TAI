"""Tests for code_security — pure checks, zero mocks."""

import pytest

from src.infrastructure.services.code_security import CodeSecurityChecker, SecurityCheckResult


@pytest.fixture()
def checker():
    return CodeSecurityChecker()


@pytest.fixture()
def strict_checker():
    return CodeSecurityChecker(strict_mode=True)


@pytest.fixture()
def no_file_ops_checker():
    return CodeSecurityChecker(allow_file_ops=False)


class TestCheckSafeCode:
    """Safe code should pass checks."""

    def test_empty_code(self, checker: CodeSecurityChecker):
        result = checker.check("")
        assert result.is_safe is True
        assert result.warnings == []
        assert result.blocked == []

    def test_whitespace_only(self, checker: CodeSecurityChecker):
        result = checker.check("   \n\n  ")
        assert result.is_safe is True

    def test_simple_math(self, checker: CodeSecurityChecker):
        result = checker.check("x = 1 + 2\nprint(x)")
        assert result.is_safe is True
        assert result.warnings == []

    def test_safe_imports(self, checker: CodeSecurityChecker):
        code = "import math\nimport json\nfrom collections import defaultdict"
        result = checker.check(code)
        assert result.is_safe is True

    def test_list_comprehension(self, checker: CodeSecurityChecker):
        code = "result = [x**2 for x in range(10)]"
        result = checker.check(code)
        assert result.is_safe is True


class TestCheckDangerousImports:
    """Dangerous imports should trigger warnings (or blocks in strict)."""

    @pytest.mark.parametrize(
        "code",
        [
            "import os",
            "import subprocess",
            "import sys",
            "import socket",
            "import ctypes",
            "import pickle",
            "import marshal",
            "from os import path",
            "from subprocess import run",
        ],
    )
    def test_dangerous_import_warns(self, checker: CodeSecurityChecker, code: str):
        result = checker.check(code)
        assert len(result.warnings) > 0 or len(result.blocked) > 0

    @pytest.mark.parametrize(
        "code",
        [
            "import os",
            "from subprocess import run",
        ],
    )
    def test_strict_mode_blocks_imports(self, strict_checker: CodeSecurityChecker, code: str):
        result = strict_checker.check(code)
        assert result.is_safe is False
        assert len(result.blocked) > 0

    def test_dunder_import(self, checker: CodeSecurityChecker):
        code = "__import__('os')"
        result = checker.check(code)
        assert len(result.warnings) > 0 or len(result.blocked) > 0


class TestCheckDangerousFunctions:
    """Dangerous functions should trigger warnings."""

    @pytest.mark.parametrize(
        "code",
        [
            "eval('1+1')",
            "exec('print(1)')",
            "compile('x', 'f', 'exec')",
            "globals()",
            "locals()",
            "x = __builtins__",
        ],
    )
    def test_dangerous_function_warns(self, checker: CodeSecurityChecker, code: str):
        result = checker.check(code)
        assert len(result.warnings) > 0 or len(result.blocked) > 0


class TestCheckDangerousCalls:
    """System calls should always be blocked."""

    @pytest.mark.parametrize(
        "code",
        [
            "os.system('rm -rf /')",
            "os.popen('ls')",
            "subprocess.run(['ls'])",
            "subprocess.call(['ls'])",
            "subprocess.Popen(['ls'])",
            "subprocess.check_output(['ls'])",
            "shutil.rmtree('/tmp/data')",
            "os.remove('file.txt')",
            "os.unlink('file.txt')",
        ],
    )
    def test_system_call_blocked(self, checker: CodeSecurityChecker, code: str):
        result = checker.check(code)
        assert result.is_safe is False
        assert len(result.blocked) > 0


class TestCommentAndStringSkipping:
    """Code in comments and strings should not trigger false positives."""

    def test_import_in_comment(self, checker: CodeSecurityChecker):
        code = "# import os\nx = 1"
        result = checker.check(code)
        assert result.is_safe is True
        assert result.warnings == []
        assert result.blocked == []

    def test_eval_in_string(self, checker: CodeSecurityChecker):
        code = 'msg = "do not use eval() in production"'
        result = checker.check(code)
        assert result.is_safe is True

    def test_import_in_docstring(self, checker: CodeSecurityChecker):
        code = '"""\nimport os\nsubprocess.run()\n"""\nx = 1'
        result = checker.check(code)
        assert result.is_safe is True


class TestFileOperations:
    """File ops detection when disallowed."""

    def test_open_allowed_by_default(self, checker: CodeSecurityChecker):
        code = "f = open('file.txt', 'r')"
        result = checker.check(code)
        # open() is allowed by default, no warning
        assert "open" not in str(result.warnings)

    def test_open_warned_when_disallowed(self, no_file_ops_checker: CodeSecurityChecker):
        code = "f = open('file.txt', 'r')"
        result = no_file_ops_checker.check(code)
        assert any("open" in w for w in result.warnings)


class TestIsSafeForExecution:
    """is_safe_for_execution: stricter than check()."""

    def test_safe_code(self, checker: CodeSecurityChecker):
        assert checker.is_safe_for_execution("x = 1 + 2") is True

    def test_warned_code_not_safe_for_execution(self, checker: CodeSecurityChecker):
        assert checker.is_safe_for_execution("import os\nx = 1") is False

    def test_blocked_code_not_safe_for_execution(self, checker: CodeSecurityChecker):
        assert checker.is_safe_for_execution("os.system('ls')") is False


class TestSanitize:
    """sanitize: remove dangerous lines."""

    def test_removes_dangerous_import(self, checker: CodeSecurityChecker):
        code = "import os\nx = 1\nimport json"
        result = checker.sanitize(code)
        assert "import os" not in result or "REMOVED" in result
        assert "x = 1" in result
        assert "import json" in result

    def test_removes_system_call(self, checker: CodeSecurityChecker):
        code = "x = 1\nos.system('ls')\ny = 2"
        result = checker.sanitize(code)
        assert "os.system" not in result or "REMOVED" in result
        assert "x = 1" in result
        assert "y = 2" in result

    def test_safe_code_unchanged(self, checker: CodeSecurityChecker):
        code = "x = 1\ny = 2\nprint(x + y)"
        result = checker.sanitize(code)
        assert result == code
