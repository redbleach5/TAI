"""Project Mapper - generates project structure map for context."""

import ast
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """Information about a function."""

    name: str
    args: list[str]
    returns: str | None = None
    docstring: str | None = None
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """Information about a class."""

    name: str
    bases: list[str]
    docstring: str | None = None
    methods: list[str] = field(default_factory=list)


@dataclass
class FileInfo:
    """Information about a code file."""

    path: str
    language: str
    imports: list[str] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)  # For JS/TS
    summary: str = ""


@dataclass
class ProjectMap:
    """Complete project map."""

    root_path: str
    files: list[FileInfo] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return project map as dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Return project map as JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        """Generate markdown representation of project map."""
        lines = [
            f"# Project Map: {self.root_path}",
            "",
            "## Statistics",
            f"- Total files: {self.stats.get('total_files', 0)}",
            f"- Total classes: {self.stats.get('total_classes', 0)}",
            f"- Total functions: {self.stats.get('total_functions', 0)}",
            "",
            "## Structure",
            "",
        ]

        # Group by directory
        by_dir: dict[str, list[FileInfo]] = {}
        for f in self.files:
            dir_path = str(Path(f.path).parent)
            if dir_path not in by_dir:
                by_dir[dir_path] = []
            by_dir[dir_path].append(f)

        for dir_path in sorted(by_dir.keys()):
            if dir_path == ".":
                lines.append("### Root")
            else:
                lines.append(f"### {dir_path}/")

            for f in by_dir[dir_path]:
                lines.append(f"\n**{Path(f.path).name}** ({f.language})")

                if f.imports:
                    imports_short = f.imports[:5]
                    lines.append(f"- Imports: {', '.join(imports_short)}")
                    if len(f.imports) > 5:
                        lines.append(f"  ...and {len(f.imports) - 5} more")

                if f.classes:
                    for cls in f.classes:
                        bases = f"({', '.join(cls.bases)})" if cls.bases else ""
                        lines.append(f"- Class `{cls.name}{bases}`")
                        if cls.methods:
                            methods_str = ", ".join(cls.methods[:5])
                            lines.append(f"  - Methods: {methods_str}")

                if f.functions:
                    for func in f.functions[:10]:
                        async_prefix = "async " if func.is_async else ""
                        args_str = ", ".join(func.args[:3])
                        if len(func.args) > 3:
                            args_str += ", ..."
                        ret = f" -> {func.returns}" if func.returns else ""
                        lines.append(f"- `{async_prefix}{func.name}({args_str}){ret}`")
                    if len(f.functions) > 10:
                        lines.append(f"  ...and {len(f.functions) - 10} more functions")

            lines.append("")

        return "\n".join(lines)


def _analyze_python_file(path: Path, content: str) -> FileInfo:
    """Analyze Python file and extract structure."""
    info = FileInfo(
        path=str(path),
        language="python",
    )

    try:
        tree = ast.parse(content)
    except SyntaxError:
        info.summary = "Failed to parse"
        return info

    for node in ast.walk(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                info.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                info.imports.append(f"{module}.{alias.name}")

        # Classes (top-level only)
        elif isinstance(node, ast.ClassDef):
            bases = [getattr(b, "id", getattr(b, "attr", "?")) for b in node.bases]
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            docstring = ast.get_docstring(node)
            info.classes.append(
                ClassInfo(
                    name=node.name,
                    bases=bases,
                    docstring=docstring[:100] if docstring else None,
                    methods=methods,
                )
            )

        # Functions (top-level only)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip if inside a class
            if any(isinstance(p, ast.ClassDef) for p in ast.walk(tree)):
                # This is a rough check, could be improved
                pass

            args = []
            for arg in node.args.args:
                arg_name = arg.arg
                if arg.annotation:
                    try:
                        arg_name += f": {ast.unparse(arg.annotation)}"
                    except Exception:
                        pass
                args.append(arg_name)

            returns = None
            if node.returns:
                try:
                    returns = ast.unparse(node.returns)
                except Exception:
                    returns = "?"

            decorators = []
            for dec in node.decorator_list:
                try:
                    decorators.append(ast.unparse(dec))
                except Exception:
                    decorators.append("?")

            info.functions.append(
                FunctionInfo(
                    name=node.name,
                    args=args,
                    returns=returns,
                    docstring=ast.get_docstring(node),
                    is_async=isinstance(node, ast.AsyncFunctionDef),
                    decorators=decorators,
                )
            )

    return info


def _analyze_typescript_file(path: Path, content: str) -> FileInfo:
    """Analyze TypeScript/JavaScript file (basic parsing)."""
    info = FileInfo(
        path=str(path),
        language="typescript" if path.suffix in (".ts", ".tsx") else "javascript",
    )

    lines = content.split("\n")

    for line in lines:
        line = line.strip()

        # Imports
        if line.startswith("import "):
            # Extract module name from import statement
            if " from " in line:
                parts = line.split(" from ")
                if len(parts) > 1:
                    module = parts[1].strip().strip("';\"")
                    info.imports.append(module)

        # Exports
        if line.startswith("export "):
            if "function " in line:
                # export function name
                match = line.split("function ")[1].split("(")[0].strip()
                info.exports.append(f"function {match}")
                info.functions.append(
                    FunctionInfo(
                        name=match,
                        args=[],
                        is_async="async " in line,
                    )
                )
            elif "class " in line:
                match = line.split("class ")[1].split(" ")[0].split("{")[0].strip()
                info.exports.append(f"class {match}")
                info.classes.append(ClassInfo(name=match, bases=[]))
            elif "const " in line or "let " in line:
                keyword = "const " if "const " in line else "let "
                match = line.split(keyword)[1].split("=")[0].split(":")[0].strip()
                info.exports.append(match)

        # Class definitions
        elif line.startswith("class ") or " class " in line:
            parts = line.split("class ")[1] if "class " in line else ""
            name = parts.split(" ")[0].split("{")[0].split("(")[0].strip()
            if name and not any(c.name == name for c in info.classes):
                bases = []
                if "extends " in line:
                    base = line.split("extends ")[1].split(" ")[0].split("{")[0].strip()
                    bases.append(base)
                info.classes.append(ClassInfo(name=name, bases=bases))

        # Function definitions
        elif "function " in line:
            if "function " in line:
                parts = line.split("function ")[1]
                name = parts.split("(")[0].strip()
                if name and not any(f.name == name for f in info.functions):
                    info.functions.append(
                        FunctionInfo(
                            name=name,
                            args=[],
                            is_async="async " in line,
                        )
                    )

    return info


def analyze_file(path: Path, content: str) -> FileInfo | None:
    """Analyze a code file and return structure info."""
    suffix = path.suffix.lower()

    if suffix == ".py":
        return _analyze_python_file(path, content)
    elif suffix in (".ts", ".tsx", ".js", ".jsx"):
        return _analyze_typescript_file(path, content)
    else:
        # Basic info for other files
        return FileInfo(
            path=str(path),
            language=suffix.lstrip(".") or "unknown",
        )


def build_project_map(
    root_path: Path,
    files: list[tuple[str, str]],
) -> ProjectMap:
    """Build project map from collected files.

    Args:
        root_path: Root path of the project
        files: List of (relative_path, content) tuples

    Returns:
        ProjectMap with structure information

    """
    project_map = ProjectMap(root_path=str(root_path))

    total_classes = 0
    total_functions = 0

    for rel_path, content in files:
        file_path = Path(rel_path)
        file_info = analyze_file(file_path, content)

        if file_info:
            project_map.files.append(file_info)
            total_classes += len(file_info.classes)
            total_functions += len(file_info.functions)

    project_map.stats = {
        "total_files": len(project_map.files),
        "total_classes": total_classes,
        "total_functions": total_functions,
    }

    return project_map


def save_project_map(project_map: ProjectMap, output_dir: str = "output") -> Path:
    """Save project map to files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save JSON
    json_path = output_path / "project_map.json"
    json_path.write_text(project_map.to_json())

    # Save Markdown
    md_path = output_path / "project_map.md"
    md_path.write_text(project_map.to_markdown())

    return md_path


def load_project_map(output_dir: str = "output") -> ProjectMap | None:
    """Load project map from file."""
    json_path = Path(output_dir) / "project_map.json"
    if not json_path.exists():
        return None

    try:
        data = json.loads(json_path.read_text())

        # Reconstruct dataclasses
        files = []
        for f_data in data.get("files", []):
            classes = [ClassInfo(**c) for c in f_data.get("classes", [])]
            functions = [FunctionInfo(**fn) for fn in f_data.get("functions", [])]
            files.append(
                FileInfo(
                    path=f_data["path"],
                    language=f_data["language"],
                    imports=f_data.get("imports", []),
                    classes=classes,
                    functions=functions,
                    exports=f_data.get("exports", []),
                    summary=f_data.get("summary", ""),
                )
            )

        return ProjectMap(
            root_path=data["root_path"],
            files=files,
            stats=data.get("stats", {}),
        )
    except Exception:
        logger.debug("Failed to load project map", exc_info=True)
        return None
