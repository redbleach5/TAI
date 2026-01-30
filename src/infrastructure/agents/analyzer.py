"""Analyzer Agent - static and LLM-powered code analysis."""

import ast
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from src.domain.ports.llm import LLMMessage, LLMPort


@dataclass
class CodeIssue:
    """Represents a code issue found during analysis."""
    
    file: str
    line: int | None
    issue_type: Literal["complexity", "duplication", "style", "bug", "security", "performance", "refactor"]
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    suggestion: str | None = None


@dataclass
class FileAnalysis:
    """Analysis result for a single file."""
    
    path: str
    lines: int
    functions: int
    classes: int
    complexity: int  # Cyclomatic complexity estimate
    issues: list[CodeIssue] = field(default_factory=list)
    

@dataclass
class ProjectAnalysis:
    """Analysis result for entire project."""
    
    total_files: int
    total_lines: int
    total_functions: int
    total_classes: int
    avg_complexity: float
    files: list[FileAnalysis] = field(default_factory=list)
    issues: list[CodeIssue] = field(default_factory=list)
    

class CodeAnalyzer:
    """Static code analyzer with LLM enhancement."""

    def __init__(self, llm: LLMPort | None = None) -> None:
        self._llm = llm

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity estimate for AST node."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, (ast.And, ast.Or)):
                complexity += 1
        return complexity

    def analyze_file(self, path: str | Path) -> FileAnalysis:
        """Analyze single Python file."""
        file_path = Path(path)
        
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return FileAnalysis(
                path=str(file_path),
                lines=0,
                functions=0,
                classes=0,
                complexity=0,
                issues=[CodeIssue(
                    file=str(file_path),
                    line=None,
                    issue_type="bug",
                    severity="high",
                    message=f"Cannot read file: {e}",
                )],
            )

        lines = len(content.splitlines())
        issues: list[CodeIssue] = []
        functions = 0
        classes = 0
        total_complexity = 0

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            return FileAnalysis(
                path=str(file_path),
                lines=lines,
                functions=0,
                classes=0,
                complexity=0,
                issues=[CodeIssue(
                    file=str(file_path),
                    line=e.lineno,
                    issue_type="bug",
                    severity="critical",
                    message=f"Syntax error: {e.msg}",
                )],
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                functions += 1
                func_complexity = self._calculate_complexity(node)
                total_complexity += func_complexity
                
                # Check for high complexity
                if func_complexity > 10:
                    issues.append(CodeIssue(
                        file=str(file_path),
                        line=node.lineno,
                        issue_type="complexity",
                        severity="high" if func_complexity > 15 else "medium",
                        message=f"Function '{node.name}' has high complexity ({func_complexity})",
                        suggestion=f"Consider breaking '{node.name}' into smaller functions",
                    ))
                
                # Check for long functions
                end_line = getattr(node, 'end_lineno', node.lineno + 50)
                func_lines = end_line - node.lineno
                if func_lines > 50:
                    issues.append(CodeIssue(
                        file=str(file_path),
                        line=node.lineno,
                        issue_type="refactor",
                        severity="medium",
                        message=f"Function '{node.name}' is too long ({func_lines} lines)",
                        suggestion="Extract parts of this function into helper functions",
                    ))
                
                # Check for too many arguments
                args_count = len(node.args.args) + len(node.args.kwonlyargs)
                if args_count > 5:
                    issues.append(CodeIssue(
                        file=str(file_path),
                        line=node.lineno,
                        issue_type="refactor",
                        severity="low",
                        message=f"Function '{node.name}' has too many parameters ({args_count})",
                        suggestion="Consider using a data class or config object",
                    ))

            elif isinstance(node, ast.ClassDef):
                classes += 1
                
                # Check for large classes
                methods = sum(1 for n in ast.walk(node) 
                             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
                if methods > 15:
                    issues.append(CodeIssue(
                        file=str(file_path),
                        line=node.lineno,
                        issue_type="refactor",
                        severity="medium",
                        message=f"Class '{node.name}' has too many methods ({methods})",
                        suggestion="Consider splitting into smaller classes",
                    ))

        # Check for missing docstrings in public functions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_"):
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        issues.append(CodeIssue(
                            file=str(file_path),
                            line=node.lineno,
                            issue_type="style",
                            severity="low",
                            message=f"Missing docstring for '{node.name}'",
                            suggestion=f"Add a docstring describing what '{node.name}' does",
                        ))

        return FileAnalysis(
            path=str(file_path),
            lines=lines,
            functions=functions,
            classes=classes,
            complexity=total_complexity,
            issues=issues,
        )

    def analyze_project(self, path: str | Path = ".") -> ProjectAnalysis:
        """Analyze entire Python project."""
        project_path = Path(path).resolve()
        
        # Find all Python files
        py_files = [
            f for f in project_path.rglob("*.py")
            if ".venv" not in str(f) 
            and "__pycache__" not in str(f)
            and "node_modules" not in str(f)
        ]

        files: list[FileAnalysis] = []
        all_issues: list[CodeIssue] = []
        total_lines = 0
        total_functions = 0
        total_classes = 0
        total_complexity = 0

        for py_file in py_files:
            analysis = self.analyze_file(py_file)
            files.append(analysis)
            all_issues.extend(analysis.issues)
            total_lines += analysis.lines
            total_functions += analysis.functions
            total_classes += analysis.classes
            total_complexity += analysis.complexity

        avg_complexity = total_complexity / total_functions if total_functions > 0 else 0

        return ProjectAnalysis(
            total_files=len(files),
            total_lines=total_lines,
            total_functions=total_functions,
            total_classes=total_classes,
            avg_complexity=round(avg_complexity, 2),
            files=files,
            issues=sorted(all_issues, key=lambda x: (
                {"critical": 0, "high": 1, "medium": 2, "low": 3}[x.severity],
                x.file,
            )),
        )

    def run_linter(self, path: str | Path = ".") -> list[CodeIssue]:
        """Run ruff linter and return issues."""
        issues: list[CodeIssue] = []
        
        try:
            result = subprocess.run(
                ["ruff", "check", str(path), "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.stdout:
                import json
                lint_results = json.loads(result.stdout)
                for item in lint_results:
                    severity = "low"
                    if item.get("code", "").startswith(("E9", "F")):
                        severity = "high"
                    elif item.get("code", "").startswith("E"):
                        severity = "medium"
                    
                    issues.append(CodeIssue(
                        file=item.get("filename", ""),
                        line=item.get("location", {}).get("row"),
                        issue_type="style",
                        severity=severity,
                        message=f"[{item.get('code')}] {item.get('message')}",
                        suggestion=item.get("fix", {}).get("message") if item.get("fix") else None,
                    ))
        except FileNotFoundError:
            pass  # ruff not installed
        except Exception:
            pass
        
        return issues

    async def llm_analyze(
        self,
        code: str,
        context: str = "",
        focus: str = "general",
    ) -> list[CodeIssue]:
        """Use LLM for deep code analysis."""
        if not self._llm:
            return []

        prompt = f"""Analyze the following Python code and identify issues.
Focus area: {focus}

{f"Context: {context}" if context else ""}

Code:
```python
{code}
```

Return a JSON array of issues found. Each issue should have:
- line: line number (or null)
- type: one of [complexity, duplication, style, bug, security, performance, refactor]
- severity: one of [low, medium, high, critical]
- message: description of the issue
- suggestion: how to fix it

Return ONLY valid JSON array, no other text."""

        messages = [
            LLMMessage(role="system", content="You are a code review expert. Output only valid JSON."),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            response = await self._llm.generate(messages=messages, model="qwen2.5-coder:32b")
            import json
            
            # Try to extract JSON from response
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            items = json.loads(content)
            issues = []
            for item in items:
                issues.append(CodeIssue(
                    file="",
                    line=item.get("line"),
                    issue_type=item.get("type", "refactor"),
                    severity=item.get("severity", "medium"),
                    message=item.get("message", ""),
                    suggestion=item.get("suggestion"),
                ))
            return issues
        except Exception:
            return []

    async def suggest_improvements(self, analysis: ProjectAnalysis) -> list[dict]:
        """Generate improvement suggestions based on analysis."""
        if not self._llm:
            # Return static suggestions based on issues
            suggestions = []
            
            # Group by severity
            critical = [i for i in analysis.issues if i.severity == "critical"]
            high = [i for i in analysis.issues if i.severity == "high"]
            
            if critical:
                suggestions.append({
                    "priority": 1,
                    "title": "Fix Critical Issues",
                    "description": f"Found {len(critical)} critical issues that need immediate attention",
                    "issues": [{"file": i.file, "line": i.line, "message": i.message} for i in critical[:5]],
                })
            
            if high:
                suggestions.append({
                    "priority": 2,
                    "title": "Address High Severity Issues",
                    "description": f"Found {len(high)} high severity issues",
                    "issues": [{"file": i.file, "line": i.line, "message": i.message} for i in high[:5]],
                })
            
            # Check overall metrics
            if analysis.avg_complexity > 8:
                suggestions.append({
                    "priority": 3,
                    "title": "Reduce Code Complexity",
                    "description": f"Average complexity is {analysis.avg_complexity}, consider refactoring complex functions",
                })
            
            return suggestions

        # Use LLM for smarter suggestions
        summary = f"""Project has {analysis.total_files} files, {analysis.total_lines} lines.
{analysis.total_functions} functions, {analysis.total_classes} classes.
Average complexity: {analysis.avg_complexity}
Issues found: {len(analysis.issues)} ({len([i for i in analysis.issues if i.severity == 'critical'])} critical, {len([i for i in analysis.issues if i.severity == 'high'])} high)

Top issues:
{chr(10).join(f'- [{i.severity}] {i.file}:{i.line} - {i.message}' for i in analysis.issues[:10])}
"""

        messages = [
            LLMMessage(
                role="system",
                content="You are a senior software architect. Suggest concrete improvements.",
            ),
            LLMMessage(
                role="user",
                content=f"""Based on this project analysis, suggest 3-5 most impactful improvements:

{summary}

Return JSON array with:
- priority: 1-5 (1 is highest)
- title: short title
- description: what to do
- estimated_effort: low/medium/high

Return ONLY valid JSON array.""",
            ),
        ]

        try:
            response = await self._llm.generate(messages=messages, model="qwen2.5-coder:32b")
            import json
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except Exception:
            return []
