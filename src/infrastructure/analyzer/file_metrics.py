"""File metrics and complexity calculation for project analysis.

Computes FileMetrics (lines, functions, classes, complexity, imports) from file path
and content. Used by ProjectAnalyzer.
"""

import ast
from pathlib import Path

from src.infrastructure.analyzer.models import FileMetrics


def extract_imports(tree: ast.AST) -> list[str]:
    """Извлекает импорты из AST."""
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def estimate_complexity(tree: ast.AST) -> int:
    """Оценивает цикломатическую сложность по AST."""
    complexity = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        elif isinstance(node, (ast.And, ast.Or)):
            complexity += 1
    return complexity


def compute_file_metrics(file_path: Path, base_path: Path) -> FileMetrics:
    """Анализирует один файл и возвращает FileMetrics.

    Args:
        file_path: Абсолютный путь к файлу.
        base_path: Базовый путь проекта (для rel_path в результатах).

    Returns:
        FileMetrics. При ошибке чтения — метрики с path и нулями.
    """
    try:
        rel_path = str(file_path.relative_to(base_path))
    except ValueError:
        rel_path = str(file_path)
    metrics = FileMetrics(path=rel_path)

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return metrics

    lines = content.split("\n")
    metrics.lines_total = len(lines)

    in_multiline_comment = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            metrics.lines_blank += 1
        elif stripped.startswith("#") or stripped.startswith("//"):
            metrics.lines_comment += 1
        elif '"""' in stripped or "'''" in stripped:
            metrics.lines_comment += 1
            if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                in_multiline_comment = not in_multiline_comment
        elif in_multiline_comment:
            metrics.lines_comment += 1
        else:
            metrics.lines_code += 1

    if file_path.suffix == ".py":
        try:
            tree = ast.parse(content)
            metrics.functions = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
            metrics.classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            metrics.imports = extract_imports(tree)
            metrics.complexity = estimate_complexity(tree)
        except SyntaxError:
            metrics.issues.append("Syntax error in file")

    return metrics
