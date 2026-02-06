"""Deep Analyzer - Cursor-like analysis: static + RAG + LLM synthesis.

Phases:
1. Key files (README, pyproject, package.json, main.py)
2. Expanded RAG (8-10 queries, 20-25 chunks)
3. Framework detection (FastAPI, React, Django)
4. Framework-specific prompts

Multi-step (A1): LLM → проблемные модули → targeted RAG → финальный синтез.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from src.application.analysis.deep_analysis_prompts import (
    DEEP_ANALYSIS_PROMPT_GENERIC,
    KEY_FILES,
    MAX_KEY_FILES_TOTAL,
    MAX_LINES_PER_FILE,
    PROMPTS_BY_FRAMEWORK,
    STEP1_MODULES_PROMPT,
)
from src.application.analysis.deep_analysis_rag import (
    A1_MAX_MODULES,
    gather_initial_rag,
    targeted_rag,
)
from src.domain.ports.llm import LLMMessage
from src.infrastructure.analyzer.coverage_collector import collect_coverage_for_analysis
from src.infrastructure.analyzer.dependency_graph import (
    build_dependency_graph,
    format_dependency_graph_markdown,
)
from src.infrastructure.analyzer.report_generator import ReportGenerator
from src.infrastructure.services.git_service import GitService

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.domain.ports.llm import LLMPort
    from src.domain.services.model_selector import ModelSelector
    from src.infrastructure.analyzer.project_analyzer import ProjectAnalyzer
    from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter


def summary_from_report(full_md: str, report_path: str) -> str:
    """Из полного отчёта выделить краткую сводку для чата (C3.1, agent tool)."""
    if not full_md or not full_md.strip():
        return f"Отчёт сохранён в `{report_path}`. Откройте файл для просмотра."
    lines = full_md.strip().split("\n")
    summary_lines: list[str] = []
    for line in lines:
        if line.strip() == "---":
            break
        if line.startswith("## ") and summary_lines:
            break
        summary_lines.append(line)
    summary_text = "\n".join(summary_lines).strip()
    if len(summary_text) > 500:
        summary_text = summary_text[:500].rsplit(" ", 1)[0] + "…"
    return f"{summary_text}\n\n📄 **Полный отчёт в проекте:** `{report_path}`"


def _parse_step1_modules(response: str) -> list[str] | None:
    """Parse JSON with problematic_modules from step 1 LLM response."""
    if not response or not response.strip():
        return None
    # Extract JSON from markdown code block if present
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", response)
    if match:
        raw = match.group(1)
    else:
        raw = response.strip()
    try:
        data = json.loads(raw)
        modules = data.get("problematic_modules")
        if isinstance(modules, list) and 1 <= len(modules) <= A1_MAX_MODULES:
            return [str(m).strip() for m in modules if m]
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _collect_key_files(project_path: Path) -> str:
    """Collect key project files for context."""
    parts: list[str] = []
    total_chars = 0

    for rel in KEY_FILES:
        if total_chars >= MAX_KEY_FILES_TOTAL:
            break
        fp = project_path / rel
        if not fp.exists() or not fp.is_file():
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()[:MAX_LINES_PER_FILE]
            excerpt = "\n".join(lines)
            if len(excerpt) + total_chars > MAX_KEY_FILES_TOTAL:
                excerpt = excerpt[: MAX_KEY_FILES_TOTAL - total_chars]
            parts.append(f"### {rel}\n```\n{excerpt}\n```")
            total_chars += len(excerpt)
        except Exception:
            continue

    return "\n\n".join(parts) if parts else "Не найдено ключевых файлов."


def _detect_framework(project_path: Path) -> str:
    """Detect project framework: fastapi, react, django, generic."""
    # Python backend
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            if "fastapi" in content.lower():
                return "fastapi"
            if "django" in content.lower():
                return "django"
            if "flask" in content.lower():
                return "generic"  # Flask — generic prompt
        except Exception:
            pass

    # Node/React frontend
    pkg = project_path / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            deps_lower = {k.lower() for k in deps}
            if "react" in deps_lower or "next" in deps_lower:
                return "react"
        except Exception:
            pass

    # Frontend subdir
    frontend_pkg = project_path / "frontend" / "package.json"
    if frontend_pkg.exists():
        try:
            data = json.loads(frontend_pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if any("react" in k.lower() for k in deps):
                return "react"
        except Exception:
            pass

    # Structure hints
    if (project_path / "src" / "api" / "routes").exists():
        return "fastapi"
    if (project_path / "frontend" / "src").exists() and (project_path / "frontend" / "package.json").exists():
        return "react"

    return "generic"


class DeepAnalyzer:
    """Cursor-like deep analysis: key files + static + RAG + LLM."""

    def __init__(
        self,
        llm: "LLMPort",
        model_selector: "ModelSelector",
        rag: "ChromaDBRAGAdapter | None" = None,
        analyzer: "ProjectAnalyzer | None" = None,
    ) -> None:
        """Initialize with LLM, model selector, optional RAG and project analyzer."""
        self._llm = llm
        self._model_selector = model_selector
        self._rag = rag
        self._analyzer = analyzer

    async def analyze(self, path: str, multi_step: bool = True) -> str:
        """Run deep analysis and return markdown report.

        Multi-step (A1): LLM identifies problematic modules → targeted RAG → final synthesis.
        Fallback: single pass when RAG unavailable or step 1 fails.
        """
        project_path = Path(path).resolve()
        if not project_path.exists() or not project_path.is_dir():
            raise ValueError(f"Invalid project path: {path}")

        # Phase 1: Gather static context
        key_files, static_report, framework = await self._gather_static_context(project_path)

        # Phase 2: Gather project-level context (map, git, coverage)
        project_map, git_context, coverage_context = await self._gather_project_context(project_path)

        # Phase 3: Gather RAG context (initial + targeted)
        rag_context, fallback_reason = await self._gather_rag_context(
            multi_step, key_files, static_report, project_map,
        )

        # Phase 4: LLM synthesis
        return await self._synthesize_with_llm(
            key_files, static_report, framework, project_map,
            git_context, coverage_context, rag_context, fallback_reason,
        )

    async def _gather_static_context(self, project_path: Path) -> tuple[str, str, str]:
        """Phase 1: Key files, static analysis, dependency graph, framework detection."""
        key_files = await asyncio.to_thread(_collect_key_files, project_path)

        if not self._analyzer:
            from src.infrastructure.analyzer.project_analyzer import ProjectAnalyzer
            self._analyzer = ProjectAnalyzer()

        analysis = await asyncio.to_thread(self._analyzer.analyze, str(project_path))
        generator = ReportGenerator()
        static_report = generator.generate_markdown(analysis)

        dep_result = await asyncio.to_thread(build_dependency_graph, str(project_path))
        dep_section = format_dependency_graph_markdown(dep_result)
        if dep_section:
            static_report = f"{static_report}\n\n{dep_section}"

        framework = await asyncio.to_thread(_detect_framework, project_path)
        return key_files, static_report, framework

    async def _gather_project_context(self, project_path: Path) -> tuple[str, str, str]:
        """Phase 2: Project map, git context, coverage."""
        # Project map
        project_map = "Не доступна. Выполните индексацию workspace для полного анализа."
        if self._rag:
            map_md = self._rag.get_project_map_markdown()
            if map_md:
                project_map = map_md[:8000]

        # Git context
        git_context = "Не репозиторий Git или Git недоступен."
        try:
            git_service = GitService(str(project_path))
            if await git_service.is_repo():
                git_context = (
                    await git_service.get_recent_changes_for_analysis(commits_limit=15, files_limit=25)
                    or git_context
                )
        except Exception as e:
            logger.debug("Git context for deep analysis failed: %s", e)

        # Coverage
        coverage_context = await asyncio.to_thread(collect_coverage_for_analysis, str(project_path))
        return project_map, git_context, coverage_context

    async def _gather_rag_context(
        self,
        multi_step: bool,
        key_files: str,
        static_report: str,
        project_map: str,
    ) -> tuple[str, str | None]:
        """Phase 3: Initial RAG + optional multi-step targeted RAG."""
        rag_context = "Не доступен. Выполните индексацию workspace."
        if self._rag:
            try:
                rag_context = await gather_initial_rag(self._rag)
            except Exception as e:
                logger.warning("RAG context for deep analysis failed: %s", e, exc_info=True)
                rag_context = "Ошибка поиска по индексу."

        # Multi-step: targeted RAG per module
        fallback_reason: str | None = None
        rag_unavailable = rag_context in (
            "Не доступен. Выполните индексацию workspace.",
            "Ошибка поиска по индексу.",
        )
        if multi_step and self._rag and not rag_unavailable:
            modules = await self._step1_identify_modules(
                key_files=key_files, static_report=static_report,
                project_map=project_map, rag_context=rag_context,
            )
            if modules:
                targeted_rag_ctx = await targeted_rag(self._rag, modules)
                if targeted_rag_ctx:
                    rag_context = (
                        f"{rag_context}\n\n---\n\n### Углублённый контекст по проблемным модулям\n{targeted_rag_ctx}"
                    )
                else:
                    fallback_reason = "углублённый контекст по модулям не получен"
            else:
                fallback_reason = "не удалось выделить проблемные модули"
        elif multi_step:
            fallback_reason = (
                "RAG недоступен (индексация workspace не выполнена)"
                if not self._rag
                else "ошибка поиска по индексу или индексация не выполнена"
            )
        return rag_context, fallback_reason

    async def _synthesize_with_llm(
        self,
        key_files: str,
        static_report: str,
        framework: str,
        project_map: str,
        git_context: str,
        coverage_context: str,
        rag_context: str,
        fallback_reason: str | None,
    ) -> str:
        """Phase 4: Build prompt and call LLM for final synthesis."""
        prompt_template = PROMPTS_BY_FRAMEWORK.get(framework, DEEP_ANALYSIS_PROMPT_GENERIC)
        prompt = prompt_template.format(
            key_files=key_files,
            static_report=static_report[:12000],
            git_context=git_context[:3000] if git_context else "Не доступен.",
            coverage_context=coverage_context,
            project_map=project_map,
            rag_context=rag_context[:12000],
        )
        messages = [
            LLMMessage(role="system", content="Ты эксперт по анализу кода. Отвечай только на русском, в Markdown."),
            LLMMessage(role="user", content=prompt),
        ]
        try:
            model, _ = await self._model_selector.select_model("анализ архитектуры проекта рефакторинг рекомендации")
            response = await self._llm.generate(messages=messages, model=model, temperature=0.3)
            result = response.content or static_report
            if fallback_reason:
                result = f"**Примечание:** Использован одношаговый режим ({fallback_reason}).\n\n---\n\n{result}"
            return result
        except Exception as e:
            return f"{static_report}\n\n---\n\n**Примечание:** LLM-анализ недоступен ({e}). Показан только статический отчёт."

    async def _step1_identify_modules(
        self,
        key_files: str,
        static_report: str,
        project_map: str,
        rag_context: str,
    ) -> list[str] | None:
        """Step 1: LLM identifies 3–5 problematic modules."""
        prompt = STEP1_MODULES_PROMPT.format(
            key_files=key_files[:4000],
            static_report=static_report[:8000],
            project_map=project_map[:6000],
            rag_context=rag_context[:6000],
        )
        messages = [
            LLMMessage(role="system", content="Ты эксперт. Отвечай только валидным JSON."),
            LLMMessage(role="user", content=prompt),
        ]
        try:
            model, _ = await self._model_selector.select_model("анализ модулей")
            response = await self._llm.generate(messages=messages, model=model, temperature=0.2)
            return _parse_step1_modules(response.content or "")
        except Exception:
            return None
