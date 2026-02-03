"""Dependency graph — A2: парсер импортов (Python/TS), граф, циклы, неиспользуемые импорты.

Используется в Deep Analyzer для включения в статический отчёт.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

# Директории для игнорирования (как в project_analyzer)
IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist",
    "build", ".next", "coverage", ".tox", "eggs",
}

PY_EXT = (".py",)
TS_JS_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs")


@dataclass
class ImportEdge:
    """Один импорт: откуда — куда (файл -> файл)."""
    from_file: str
    to_file: str
    name: str  # импортированное имя/модуль


@dataclass
class DependencyGraphResult:
    """Результат построения графа зависимостей."""
    edges: list[ImportEdge] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    unused_imports: list[tuple[str, str]] = field(default_factory=list)  # (file, import_name)
    node_count: int = 0
    edge_count: int = 0


def _collect_code_files(project_path: Path) -> tuple[list[Path], list[Path]]:
    """Собирает пути к Python и TS/JS файлам (относительно project_path не меняем — вернём Path)."""
    py_files: list[Path] = []
    ts_files: list[Path] = []

    for p in project_path.rglob("*"):
        if not p.is_file():
            continue
        if any(ignored in p.parts for ignored in IGNORE_DIRS):
            continue
        if p.suffix.lower() in PY_EXT:
            py_files.append(p)
        elif p.suffix.lower() in TS_JS_EXT:
            ts_files.append(p)

    return py_files, ts_files


def _module_to_possible_paths(module: str, base: Path) -> list[Path]:
    """Преобразует имя модуля Python в возможные пути к файлу."""
    parts = module.split(".")
    candidates: list[Path] = []
    # file: base / src / api / routes.py
    file_path = base / parts[0]
    for part in parts[1:]:
        file_path = file_path / part
    candidates.append(file_path.with_suffix(".py"))
    # package: base / src / api / routes / __init__.py
    candidates.append(file_path / "__init__.py")
    return [c for c in candidates if c.is_relative_to(base)]


def _resolve_python_import(
    module: str,
    from_file: Path,
    base_path: Path,
    py_files_set: set[Path],
) -> Path | None:
    """Разрешает импорт Python до пути к файлу (относительно base_path)."""
    # Относительный импорт: from .foo import bar -> от директории текущего файла
    if module.startswith("."):
        parent = from_file.parent
        rel = module.lstrip(".")
        if not rel:
            # from . import ...
            target = parent / "__init__.py"
        else:
            parts = rel.split(".")
            target = parent
            for p in parts:
                target = target / p
            target_py = target.with_suffix(".py")
            target_init = target / "__init__.py"
            if target_py in py_files_set:
                return target_py
            if target_init in py_files_set:
                return target_init
            return None

    # Абсолютный: ищем от корня проекта
    for cand in _module_to_possible_paths(module, base_path):
        if cand in py_files_set:
            return cand
    # Попробуем от директории файла (локальный пакет)
    parent = from_file.parent
    rel_parts = module.split(".")
    for i in range(len(rel_parts), 0, -1):
        sub = parent / Path(*rel_parts[:i])
        if (sub.with_suffix(".py") in py_files_set):
            return sub.with_suffix(".py")
        if (sub / "__init__.py") in py_files_set:
            return sub / "__init__.py"
    return None


def _extract_python_imports(content: str) -> list[tuple[str, list[str]]]:
    """Извлекает импорты из Python-кода: (module, [names])."""
    result: list[tuple[str, list[str]]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append((alias.name, [alias.asname or alias.name]))
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            names = [a.asname or a.name for a in node.names]
            result.append((node.module, names))
    return result


def _extract_ts_imports(content: str) -> list[str]:
    """Извлекает пути/модули из TypeScript/JS (import/require)."""
    result: list[str] = []
    # import x from 'path'; import { a } from "path"; import 'side-effect';
    for m in re.finditer(
        r"""import\s+(?:(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+)?['"]([^'"]+)['"]""",
        content,
    ):
        result.append(m.group(1))
    # require('path')
    for m in re.finditer(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", content):
        result.append(m.group(1))
    return result


def _resolve_ts_import(
    spec: str,
    from_file: Path,
    base_path: Path,
    ts_files_set: set[Path],
) -> Path | None:
    """Разрешает импорт TS/JS до пути к файлу. spec — строка из import/require."""
    # Внешние пакеты (node_modules) — пропускаем
    if not spec.startswith(".") and not spec.startswith("/"):
        return None

    from_dir = from_file.parent
    if spec.startswith("."):
        resolved = (from_dir / spec).resolve()
    else:
        resolved = (base_path / spec.lstrip("/")).resolve()

    # Попробуем с расширениями
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ""):
        candidate = resolved.with_suffix(ext) if ext else resolved
        if candidate in ts_files_set:
            return candidate
        if not candidate.suffix and candidate.is_file():
            return candidate
    # index
    for name in ("index.ts", "index.tsx", "index.js", "index.jsx"):
        index_path = resolved / name
        if index_path in ts_files_set:
            return index_path
    return None


def _find_cycles(adj: dict[str, list[str]]) -> list[list[str]]:
    """Поиск циклов в графе (DFS). Возвращает список циклов (каждый — список узлов)."""
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()
    path: list[str] = []
    node_to_index: dict[str, int] = {}

    def dfs(node: str) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        node_to_index[node] = len(path) - 1

        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_stack:
                start = node_to_index[neighbor]
                cycle = path[start:] + [neighbor]
                cycles.append(cycle)

        path.pop()
        rec_stack.discard(node)
        del node_to_index[node]

    for n in adj:
        if n not in visited:
            dfs(n)

    return cycles


def _find_unused_python_imports(
    rel_path: str,
    content: str,
    imports: list[tuple[str, list[str]]],
) -> list[tuple[str, str]]:
    """Для Python: неиспользуемые импорты (имена не встречаются в коде после импортов)."""
    unused: list[tuple[str, str]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return unused

    # Собираем все имена, которые используются в коде (кроме определений и импортов)
    used_names: set[str] = set()
    import_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in (node.names if hasattr(node, "names") else getattr(node, "names", [])):
                name = alias.asname or alias.name
                import_names.add(name)
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used_names.add(node.id)
        if isinstance(node, ast.Attribute):
            # только первый сегмент атрибута (a.b.c -> a)
            n = node
            while isinstance(n, ast.Attribute):
                n = n.value
            if isinstance(n, ast.Name):
                used_names.add(n.id)

    for _module, names in imports:
        for name in names:
            if name not in used_names and name in import_names:
                unused.append((rel_path, name))
    return unused


def build_dependency_graph(project_path: str | Path) -> DependencyGraphResult:
    """Строит граф зависимостей по проекту, находит циклы и неиспользуемые импорты."""
    base = Path(project_path).resolve()
    if not base.is_dir():
        return DependencyGraphResult()

    py_files, ts_files = _collect_code_files(base)
    py_set = set(py_files)
    ts_set = set(ts_files)

    edges: list[ImportEdge] = []
    unused: list[tuple[str, str]] = []

    # Python
    for fp in py_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel_from = str(fp.relative_to(base)).replace("\\", "/")
        imports = _extract_python_imports(content)
        for module, names in imports:
            resolved = _resolve_python_import(module, fp, base, py_set)
            if resolved is not None:
                rel_to = str(resolved.relative_to(base)).replace("\\", "/")
                if rel_from != rel_to:
                    edges.append(ImportEdge(from_file=rel_from, to_file=rel_to, name=module))
        unused.extend(_find_unused_python_imports(rel_from, content, imports))

    # Deduplicate unused by (file, name)
    seen_unused: set[tuple[str, str]] = set()
    unique_unused: list[tuple[str, str]] = []
    for item in unused:
        key = (item[0], item[1])
        if key not in seen_unused:
            seen_unused.add(key)
            unique_unused.append(item)
    unused = unique_unused

    # TypeScript/JS
    for fp in ts_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel_from = str(fp.relative_to(base)).replace("\\", "/")
        for spec in _extract_ts_imports(content):
            resolved = _resolve_ts_import(spec, fp, base, ts_set)
            if resolved is not None:
                rel_to = str(resolved.relative_to(base)).replace("\\", "/")
                if rel_from != rel_to:
                    edges.append(ImportEdge(from_file=rel_from, to_file=rel_to, name=spec))

    # Граф: from_file -> [to_file, ...]
    adj: dict[str, list[str]] = {}
    for e in edges:
        adj.setdefault(e.from_file, []).append(e.to_file)
    for n in list(adj):
        adj[n] = list(dict.fromkeys(adj[n]))

    cycles = _find_cycles(adj)
    nodes = set(adj) | {e.to_file for e in edges}

    return DependencyGraphResult(
        edges=edges,
        cycles=cycles,
        unused_imports=unused,
        node_count=len(nodes),
        edge_count=len(edges),
    )


def format_dependency_graph_markdown(result: DependencyGraphResult) -> str:
    """Форматирует результат графа зависимостей в Markdown для отчёта."""
    if result.node_count == 0 and not result.cycles and not result.unused_imports:
        return ""

    parts = ["## 📦 Граф зависимостей (A2)\n"]

    parts.append(f"- Узлов: {result.node_count}, рёбер (импортов): {result.edge_count}\n")

    if result.cycles:
        parts.append("### Циклы зависимостей\n")
        for i, cycle in enumerate(result.cycles[:15], 1):
            cycle_str = " → ".join(f"`{n}`" for n in cycle)
            parts.append(f"{i}. {cycle_str}\n")
        if len(result.cycles) > 15:
            parts.append(f"*… и ещё {len(result.cycles) - 15} циклов*\n")
    else:
        parts.append("### Циклы\n\nЦиклов не обнаружено.\n")

    if result.unused_imports:
        parts.append("### Возможные неиспользуемые импорты (Python)\n")
        by_file: dict[str, list[str]] = {}
        for file_path, name in result.unused_imports[:50]:
            by_file.setdefault(file_path, []).append(name)
        for file_path, names in list(by_file.items())[:20]:
            names_str = ", ".join(names)
            parts.append(f"- `{file_path}`: {names_str}\n")
        if len(result.unused_imports) > 50:
            parts.append(f"*… всего {len(result.unused_imports)} позиций*\n")
    else:
        parts.append("### Неиспользуемые импорты\n\nНе обнаружено.\n")

    return "\n".join(parts)
