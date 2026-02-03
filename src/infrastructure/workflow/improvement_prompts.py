"""Prompt builders for improvement workflow (plan and code steps)."""

from typing import Any

PLAN_SYSTEM = "You are a senior Python developer. Create concise improvement plans."
CODE_SYSTEM = "You are a Python expert. Output only valid Python code."


def _rag_section_for_plan(state: dict[str, Any]) -> str:
    """Build RAG/project/related-files section for plan prompt."""
    parts = []
    project_map = state.get("project_map") or ""
    if project_map:
        parts.append(f"\nProject structure:\n{project_map[:1500]}\n\n")
    rag_context = state.get("rag_context") or ""
    if rag_context:
        parts.append(
            """
Relevant code from project (follow similar patterns):
{rag_context}

""".format(rag_context=rag_context)
        )
    related = state.get("related_files_context") or ""
    if related:
        parts.append(
            """
Related files (imports, tests - consider when planning):
{related}

""".format(related=related)
        )
    return "".join(parts)


def build_plan_prompt(state: dict[str, Any]) -> str:
    """Build user prompt for the plan step."""
    issue = state.get("issue") or {}
    original_code = state.get("original_code", "")
    rag_section = _rag_section_for_plan(state)
    return f"""You need to improve this code to fix the following issue:

Issue: {issue.get("message", "General improvement")}
Severity: {issue.get("severity", "medium")}
Type: {issue.get("issue_type", "refactor")}
Suggestion: {issue.get("suggestion", "Improve code quality")}
{rag_section}
Original code:
```python
{original_code}
```

Create a brief step-by-step plan to fix this issue. Be specific about what changes to make.
"""


def _rag_section_for_code(state: dict[str, Any]) -> str:
    """Build RAG/project/related section for code prompt."""
    parts = []
    project_map = state.get("project_map") or ""
    if project_map:
        parts.append(f"\nProject structure:\n{project_map[:1200]}\n\n")
    rag_context = state.get("rag_context") or ""
    if rag_context:
        parts.append(
            """
Project context (follow similar patterns):
{rag_context}

""".format(rag_context=rag_context[:2000])
        )
    related = state.get("related_files_context") or ""
    if related:
        parts.append(
            """
Related files (preserve imports, consider callers/tests):
{related}

""".format(related=related[:2000])
        )
    return "".join(parts)


def build_code_prompt(state: dict[str, Any]) -> str:
    """Build user prompt for the code step (with optional retry context)."""
    issue = state.get("issue") or {}
    original_code = state.get("original_code", "")
    plan = state.get("plan", "")
    validation_output = state.get("validation_output", "")
    retry_count = state.get("retry_count", 0)
    error_rag_context = state.get("error_rag_context", "")

    retry_context = ""
    if retry_count > 0 and validation_output:
        retry_context = f"""

PREVIOUS ATTEMPT FAILED. Full error / stack trace:
```
{validation_output}
```
Fix the issues and try again.
"""
        if error_rag_context:
            retry_context += f"""

Similar code from codebase (may help fix this error):
{error_rag_context}
"""

    rag_section = _rag_section_for_code(state)
    return f"""Improve this Python code following the plan below.

Issue to fix: {issue.get("message", "General improvement")}

Plan:
{plan}
{rag_section}
Original code:
```python
{original_code}
```
{retry_context}
Output ONLY the improved Python code. No markdown, no explanations.
Preserve the overall structure and imports. Make minimal necessary changes.
"""
