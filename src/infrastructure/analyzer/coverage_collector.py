"""A4: Collect test coverage (pytest-cov/coverage) for analysis prompt.

Runs coverage in project directory and returns formatted report for LLM.
"""

import subprocess
from pathlib import Path

COVERAGE_TIMEOUT = 90  # seconds for pytest
COVERAGE_REPORT_MAX_CHARS = 4000  # limit for prompt


def collect_coverage_for_analysis(project_path: str) -> str:
    """Run pytest with coverage and return formatted report for analysis prompt.

    - If coverage is not installed or no Python tests: returns short message.
    - Runs: coverage run -m pytest tests/ -q --tb=no; coverage report -m
    - Limits output size for prompt.
    """
    path = Path(project_path).resolve()
    if not path.exists() or not path.is_dir():
        return "Путь проекта недоступен."

    # Only for Python projects: pyproject.toml or setup.py and tests/
    has_pyproject = (path / "pyproject.toml").exists() or (path / "setup.py").exists()
    tests_dir = path / "tests"
    if not has_pyproject or not tests_dir.is_dir():
        return "Покрытие не измерено: не Python-проект или нет папки tests/."

    try:
        # Run coverage (creates .coverage in project_path)
        run_result = subprocess.run(
            ["coverage", "run", "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=COVERAGE_TIMEOUT,
        )
        # Even if pytest failed, we may have partial coverage
        report_result = subprocess.run(
            ["coverage", "report", "-m"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if report_result.returncode != 0:
            if "No module named 'coverage'" in (report_result.stderr or "") or "coverage: command not found" in (report_result.stderr or ""):
                return "Покрытие не измерено: установите coverage (pip install coverage)."
            if "No data to report" in (report_result.stdout or report_result.stderr or ""):
                return "Покрытие не измерено: тесты не запускались или не собрали данные (проверьте pytest)."
            return f"Покрытие не измерено: {report_result.stderr or report_result.stdout or 'ошибка coverage report'}"

        out = (report_result.stdout or "").strip()
        if not out:
            return "Покрытие не измерено: пустой отчёт coverage."

        # Truncate for prompt
        if len(out) > COVERAGE_REPORT_MAX_CHARS:
            out = out[:COVERAGE_REPORT_MAX_CHARS] + "\n... (обрезано)"
        return f"```\n{out}\n```\n(Запуск: coverage run -m pytest tests/ -q; exit code pytest: {run_result.returncode})"
    except subprocess.TimeoutExpired:
        return "Покрытие не измерено: запуск тестов превысил таймаут."
    except FileNotFoundError:
        return "Покрытие не измерено: установите coverage (pip install coverage)."
    except Exception as e:
        return f"Покрытие не измерено: {e!s}"
