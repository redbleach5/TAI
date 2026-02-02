"""Security scanner for project analysis.

Scans file content for known security patterns (eval, exec, hardcoded secrets, etc.)
and returns list of SecurityIssue. Used by ProjectAnalyzer.
"""

import logging
import re
from pathlib import Path

from src.infrastructure.analyzer.models import SecurityIssue

logger = logging.getLogger(__name__)

# Паттерны безопасности (word boundaries для точности)
SECURITY_PATTERNS: list[tuple[str, str, str, str]] = [
    # Critical
    (r"(?<!['\"\w])eval\s*\([^)]+\)", "critical", "Вызов eval()", "Использовать ast.literal_eval() или безопасные альтернативы"),
    (r"(?<![\w.])exec\s*\([^)]+\)", "critical", "Вызов exec()", "Переструктурировать код, избегать динамического выполнения"),
    (r"subprocess\.(call|run|Popen).*shell\s*=\s*True", "critical", "Риск shell injection", "Использовать shell=False и передавать аргументы списком"),
    (r"os\.system\s*\([^)]+\)", "critical", "Выполнение OS-команд", "Использовать subprocess с shell=False"),
    # High
    (r"pickle\.loads?\s*\(", "high", "Десериализация pickle", "Использовать JSON или безопасный формат"),
    (r"yaml\.load\s*\([^)]*Loader\s*=\s*None", "high", "Небезопасная загрузка YAML", "Использовать yaml.safe_load()"),
    (r"(?<!['\"\w])__import__\s*\(", "high", "Динамический импорт", "Использовать статические импорты"),
    (r"password\s*=\s*['\"][a-zA-Z0-9]{8,}['\"]", "high", "Пароль в коде", "Использовать переменные окружения или secrets manager"),
    (r"api[_-]?key\s*=\s*['\"][a-zA-Z0-9]{16,}['\"]", "high", "API-ключ в коде", "Использовать переменные окружения"),
    # Medium
    (r"verify\s*=\s*False", "medium", "Отключена проверка SSL", "Включить проверку SSL"),
    # Low
    (r"\b(TODO|FIXME|HACK|XXX)\b:", "low", "Маркер TODO/FIXME", "Исправить отложенные задачи"),
]

# Pre-compiled at module load
_COMPILED_PATTERNS: list[tuple[re.Pattern[str], str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), severity, issue, rec)
    for pattern, severity, issue, rec in SECURITY_PATTERNS
]


def check_file_security(file_path: Path, base_path: Path) -> list[SecurityIssue]:
    """Проверяет файл на проблемы безопасности.

    Args:
        file_path: Абсолютный путь к файлу.
        base_path: Базовый путь проекта (для rel_path в результатах).

    Returns:
        Список SecurityIssue. Пустой для документации/тестов или при ошибке чтения.
    """
    issues: list[SecurityIssue] = []
    try:
        rel_path = str(file_path.relative_to(base_path))
    except ValueError:
        return issues

    # Пропускаем документацию и тесты
    if file_path.suffix in (".md", ".mdx", ".rst", ".txt"):
        return issues
    path_lower = rel_path.lower()
    if any(part in path_lower for part in ["test", "tests", "spec", "__tests__"]) and file_path.suffix == ".py":
        return issues

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.debug("Failed to read %s: %s", rel_path, e)
        return issues

    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(("#", "//")):
            continue
        if stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        for compiled_pattern, severity, issue, recommendation in _COMPILED_PATTERNS:
            if compiled_pattern.search(line):
                issues.append(SecurityIssue(
                    severity=severity,
                    file=rel_path,
                    line=i,
                    issue=issue,
                    recommendation=recommendation,
                ))
    return issues
