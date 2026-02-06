"""Code smells detection for project analyzer.

Finds code smell patterns (long params, deep nesting, bare except, etc.)
in Python files. Used by ProjectAnalyzer.
"""

import re
from pathlib import Path

CODE_SMELL_PATTERNS: list[tuple[str, str]] = [
    (r"def\s+\w+\([^)]{100,}\)", "Длинный список параметров (>5)"),
    (r"if\s+.*:\s*\n\s+if\s+.*:\s*\n\s+if", "Глубокая вложенность (3+ уровня)"),
    (r"except\s*:", "Пустой except"),
    (r"from\s+\w+\s+import\s+\*", "Импорт через *"),
    (r"global\s+\w+", "Использование global"),
    (r"#.*type:\s*ignore", "Комментарий type: ignore"),
]

_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.MULTILINE), desc) for pattern, desc in CODE_SMELL_PATTERNS
]

MAX_SMELLS = 20


def find_code_smells(files: list[Path], base_path: Path) -> list[str]:
    """Находит code smells в Python-файлах.

    Args:
        files: Список путей к файлам.
        base_path: Базовый путь проекта (для rel_path в результатах).

    Returns:
        Список строк вида "rel_path: описание (N occurrences)", не более MAX_SMELLS.

    """
    smells: list[str] = []
    for file_path in files:
        if file_path.suffix != ".py":
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            rel_path = str(file_path.relative_to(base_path))
        except ValueError:
            continue
        for compiled_pattern, description in _COMPILED:
            matches = compiled_pattern.findall(content)
            if matches:
                smells.append(f"{rel_path}: {description} ({len(matches)} occurrences)")
    return smells[:MAX_SMELLS]
