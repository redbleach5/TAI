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
import re
from pathlib import Path
from typing import TYPE_CHECKING

from src.domain.ports.llm import LLMMessage
from src.infrastructure.analyzer.project_analyzer import get_analyzer
from src.infrastructure.analyzer.report_generator import ReportGenerator

if TYPE_CHECKING:
    from src.domain.ports.llm import LLMPort
    from src.domain.services.model_selector import ModelSelector
    from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter


# Key files to include for project context (first N lines each)
KEY_FILES = [
    "README.md",
    "readme.md",
    "pyproject.toml",
    "package.json",
    "main.py",
    "app.py",
    "run.py",
    "src/main.py",
    "src/app.py",
    "frontend/package.json",
]
MAX_LINES_PER_FILE = 80
MAX_KEY_FILES_TOTAL = 4000  # chars

# RAG queries - expanded for better coverage
RAG_QUERIES = [
    "архитектура entry points main",
    "конфигурация настройки config",
    "API routes handlers endpoints",
    "сложные функции сложность complexity",
    "ошибки обработка exceptions error handling",
    "зависимости импорты imports dependencies",
    "тесты tests pytest",
    "модели данные models schema",
]
RAG_CHUNKS_PER_QUERY = 3
RAG_MAX_CHUNKS = 25
RAG_MIN_SCORE = 0.35

# Multi-step: targeted RAG per module
A1_MAX_MODULES = 5
A1_CHUNKS_PER_MODULE = 5
A1_TARGETED_QUERY_TEMPLATE = "код логика проблемы рефакторинг {module}"

# Step 1 prompt: identify problematic modules
STEP1_MODULES_PROMPT = """Ты — эксперт по анализу кода. На основе статического анализа и карты проекта определи 3–5 **наиболее проблемных модулей** (файлов или директорий), требующих углублённого анализа.

## Входные данные

### Ключевые файлы
{key_files}

### Статический анализ
{static_report}

### Карта проекта
{project_map}

### Релевантный код (начальный RAG)
{rag_context}

---

## Задача

Верни **только** валидный JSON, без markdown и пояснений:
```json
{{"problematic_modules": ["путь/к/файлу1.py", "src/api/routes", "frontend/src/App.tsx"]}}
```

Правила:
- 3–5 путей (относительно корня проекта)
- Файлы: src/main.py, frontend/src/App.tsx
- Директории: src/api/routes, frontend/src/features
- Только пути из карты проекта или статического анализа
- Приоритет: сложность, ошибки, дублирование, архитектурные проблемы"""

# Framework-specific prompts
DEEP_ANALYSIS_PROMPT_GENERIC = """Ты — эксперт по анализу кодовых баз уровня Cursor AI. Проанализируй проект и дай **практичные, приоритизированные** рекомендации.

## Входные данные

### Ключевые файлы проекта
{key_files}

### Статический анализ
{static_report}

### Карта проекта (структура)
{project_map}

### Релевантный код из RAG
{rag_context}

---

## Задача

Сформируй отчёт на русском языке в формате Markdown. Фокус на **действиях**, а не на очевидной статистике.

### 1. Краткое резюме (2-3 предложения)
Главный вывод: что в порядке, что требует внимания.

### 2. Топ-5 приоритетных проблем
Для каждой: файл:строка, суть проблемы, **конкретная рекомендация** (что сделать).
Формат:
- `**файл:строка**` — описание. Рекомендация: ...

### 3. Архитектурные наблюдения
Связи между модулями, потенциальные узкие места, дублирование.

### 4. Рекомендации по улучшению
3-5 конкретных шагов с приоритетом (высокий/средний/низкий).

### 5. Сильные стороны
Что уже хорошо сделано.

Пиши кратко, по делу. Избегай общих фраз вроде «улучшить качество кода» — давай конкретику."""

DEEP_ANALYSIS_PROMPT_FASTAPI = """Ты — эксперт по FastAPI и Python backend. Проанализируй проект и дай **практичные** рекомендации.

## Входные данные

### Ключевые файлы
{key_files}

### Статический анализ
{static_report}

### Карта проекта
{project_map}

### Релевантный код
{rag_context}

---

## Задача

Отчёт на русском, Markdown. Учитывай специфику FastAPI:
- Routes, dependencies, Pydantic models
- Async/await, middleware
- Обработка ошибок, валидация
- Безопасность (CORS, auth)

### 1. Краткое резюме
### 2. Топ-5 проблем (файл:строка + рекомендация)
### 3. Архитектура API (роуты, слои)
### 4. Рекомендации (приоритет)
### 5. Сильные стороны"""

DEEP_ANALYSIS_PROMPT_REACT = """Ты — эксперт по React/TypeScript frontend. Проанализируй проект и дай **практичные** рекомендации.

## Входные данные

### Ключевые файлы
{key_files}

### Статический анализ
{static_report}

### Карта проекта
{project_map}

### Релевантный код
{rag_context}

---

## Задача

Отчёт на русском, Markdown. Учитывай специфику React:
- Components, hooks, state management
- TypeScript типизация
- Производительность, мемоизация
- Структура папок, переиспользование

### 1. Краткое резюме
### 2. Топ-5 проблем (файл:строка + рекомендация)
### 3. Архитектура компонентов
### 4. Рекомендации (приоритет)
### 5. Сильные стороны"""

DEEP_ANALYSIS_PROMPT_DJANGO = """Ты — эксперт по Django. Проанализируй проект и дай **практичные** рекомендации.

## Входные данные

### Ключевые файлы
{key_files}

### Статический анализ
{static_report}

### Карта проекта
{project_map}

### Релевантный код
{rag_context}

---

## Задача

Отчёт на русском, Markdown. Учитывай специфику Django:
- Models, migrations, ORM
- Views, serializers, permissions
- Settings, middleware
- Тесты, fixtures

### 1. Краткое резюме
### 2. Топ-5 проблем (файл:строка + рекомендация)
### 3. Архитектура приложений
### 4. Рекомендации (приоритет)
### 5. Сильные стороны"""

PROMPTS_BY_FRAMEWORK = {
    "fastapi": DEEP_ANALYSIS_PROMPT_FASTAPI,
    "react": DEEP_ANALYSIS_PROMPT_REACT,
    "django": DEEP_ANALYSIS_PROMPT_DJANGO,
    "generic": DEEP_ANALYSIS_PROMPT_GENERIC,
}


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
    ) -> None:
        self._llm = llm
        self._model_selector = model_selector
        self._rag = rag

    async def analyze(self, path: str, multi_step: bool = True) -> str:
        """Run deep analysis and return markdown report.

        Multi-step (A1): LLM identifies problematic modules → targeted RAG → final synthesis.
        Fallback: single pass when RAG unavailable or step 1 fails.
        """
        project_path = Path(path).resolve()
        if not project_path.exists() or not project_path.is_dir():
            raise ValueError(f"Invalid project path: {path}")

        # 0. Key files
        key_files = await asyncio.to_thread(_collect_key_files, project_path)

        # 1. Static analysis
        analyzer = get_analyzer()
        analysis = await asyncio.to_thread(analyzer.analyze, str(project_path))
        generator = ReportGenerator()
        static_report = generator.generate_markdown(analysis)

        # 2. Framework detection
        framework = await asyncio.to_thread(_detect_framework, project_path)

        # 3. Project map (if RAG indexed)
        project_map = "Не доступна. Выполните индексацию workspace для полного анализа."
        if self._rag:
            map_md = self._rag.get_project_map_markdown()
            if map_md:
                project_map = map_md[:8000]

        # 4. Initial RAG context (expanded)
        rag_context = "Не доступен. Выполните индексацию workspace."
        if self._rag:
            try:
                rag_context = await self._gather_initial_rag()
            except Exception:
                rag_context = "Ошибка поиска по индексу."

        # 5. Multi-step: targeted RAG per module (A1)
        used_multi_step = False
        fallback_reason: str | None = None
        if multi_step and self._rag and rag_context not in (
            "Не доступен. Выполните индексацию workspace.",
            "Ошибка поиска по индексу.",
        ):
            modules = await self._step1_identify_modules(
                key_files=key_files,
                static_report=static_report,
                project_map=project_map,
                rag_context=rag_context,
            )
            if modules:
                targeted_rag = await self._step2_targeted_rag(modules)
                if targeted_rag:
                    used_multi_step = True
                    rag_context = f"{rag_context}\n\n---\n\n### Углублённый контекст по проблемным модулям\n{targeted_rag}"
                else:
                    fallback_reason = "углублённый контекст по модулям не получен"
            else:
                fallback_reason = "не удалось выделить проблемные модули"
        elif multi_step:
            if not self._rag:
                fallback_reason = "RAG недоступен (индексация workspace не выполнена)"
            else:
                fallback_reason = "ошибка поиска по индексу или индексация не выполнена"

        # 6. LLM synthesis (framework-specific prompt)
        prompt_template = PROMPTS_BY_FRAMEWORK.get(framework, DEEP_ANALYSIS_PROMPT_GENERIC)
        prompt = prompt_template.format(
            key_files=key_files,
            static_report=static_report[:12000],
            project_map=project_map,
            rag_context=rag_context[:12000],
        )

        messages = [
            LLMMessage(role="system", content="Ты эксперт по анализу кода. Отвечай только на русском, в Markdown."),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            model, _ = await self._model_selector.select_model(
                "анализ архитектуры проекта рефакторинг рекомендации"
            )
            response = await self._llm.generate(
                messages=messages,
                model=model,
                temperature=0.3,
            )
            result = response.content or static_report
            if fallback_reason:
                result = f"**Примечание:** Использован одношаговый режим ({fallback_reason}).\n\n---\n\n{result}"
            return result
        except Exception as e:
            return f"{static_report}\n\n---\n\n**Примечание:** LLM-анализ недоступен ({e}). Показан только статический отчёт."

    async def _gather_initial_rag(self) -> str:
        """Gather initial RAG context from expanded queries."""
        chunks_by_query: list[str] = []
        seen_sources: set[str] = set()
        for q in RAG_QUERIES:
            if len(chunks_by_query) >= RAG_MAX_CHUNKS:
                break
            results = await self._rag.search(q, limit=RAG_CHUNKS_PER_QUERY, min_score=RAG_MIN_SCORE)
            for c in results:
                src = c.metadata.get("source", "")
                if src not in seen_sources:
                    seen_sources.add(src)
                    chunks_by_query.append(f"### {src}\n```\n{c.content[:700]}\n```")
                    if len(chunks_by_query) >= RAG_MAX_CHUNKS:
                        break
        return "\n\n".join(chunks_by_query) if chunks_by_query else "Не найдено релевантных чанков."

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

    async def _step2_targeted_rag(self, modules: list[str]) -> str:
        """Step 2: RAG search per module for deeper context."""
        parts: list[str] = []
        seen: set[str] = set()
        for module in modules[:A1_MAX_MODULES]:
            query = A1_TARGETED_QUERY_TEMPLATE.format(module=module)
            try:
                results = await self._rag.search(
                    query, limit=A1_CHUNKS_PER_MODULE, min_score=RAG_MIN_SCORE
                )
                for c in results:
                    src = c.metadata.get("source", "")
                    key = f"{src}:{c.content[:100]}"
                    if key not in seen:
                        seen.add(key)
                        parts.append(f"#### {module}\n```\n{c.content[:600]}\n```")
            except Exception:
                continue
        return "\n\n".join(parts) if parts else ""
