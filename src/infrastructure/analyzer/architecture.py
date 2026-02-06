"""Architecture analysis for project analyzer.

Builds ArchitectureInfo (layers, dependencies, entry points, config files)
from project path and file list. Used by ProjectAnalyzer.
"""

import ast
from pathlib import Path

from src.infrastructure.analyzer.file_metrics import extract_imports
from src.infrastructure.analyzer.models import ArchitectureInfo

ENTRY_PATTERNS = ["main.py", "app.py", "run.py", "index.py", "__main__.py", "cli.py"]
CONFIG_PATTERNS = ["*.toml", "*.yaml", "*.yml", "*.json", "*.ini", "*.env*"]
STDLIB_PREFIXES = ("os", "sys", "re", "json", "typing", "dataclass")


def analyze_architecture(path: Path, files: list[Path]) -> ArchitectureInfo:
    """Анализирует архитектуру проекта.

    Args:
        path: Корень проекта.
        files: Список путей к файлам проекта.

    Returns:
        ArchitectureInfo с layers, dependencies, entry_points, config_files.

    """
    arch = ArchitectureInfo()

    for file_path in files:
        try:
            rel = file_path.relative_to(path)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) > 1:
            layer = parts[0]
            if layer not in arch.layers:
                arch.layers[layer] = []
            arch.layers[layer].append(str(rel))

    for file_path in files:
        if file_path.name in ENTRY_PATTERNS:
            try:
                arch.entry_points.append(str(file_path.relative_to(path)))
            except ValueError:
                pass

    for file_path in files:
        for pattern in CONFIG_PATTERNS:
            if file_path.match(pattern):
                try:
                    arch.config_files.append(str(file_path.relative_to(path)))
                except ValueError:
                    pass
                break

    for file_path in files:
        if file_path.suffix != ".py":
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)
            imports = extract_imports(tree)
            try:
                rel_path = str(file_path.relative_to(path))
            except ValueError:
                continue
            local_imports = [i for i in imports if not i.startswith(STDLIB_PREFIXES)]
            if local_imports:
                arch.dependencies[rel_path] = local_imports[:10]
        except (SyntaxError, OSError):
            continue

    return arch
