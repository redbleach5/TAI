"""Prompt templates and constants for deep analysis.

Used by DeepAnalyzer: key files list, RAG step1 prompt, framework-specific
final report prompts.
"""

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

# Step 1 prompt: identify problematic modules (A1 multi-step)
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

# Framework-specific final report prompts
DEEP_ANALYSIS_PROMPT_GENERIC = """Ты — эксперт по анализу кодовых баз уровня Cursor AI. Проанализируй проект и дай **практичные, приоритизированные** рекомендации.

## Входные данные

### Ключевые файлы проекта
{key_files}

### Статический анализ
{static_report}

### Git (A3: недавние коммиты и изменённые файлы)
{git_context}

### Покрытие тестами (A4: pytest-cov/coverage)
{coverage_context}

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

### Git (A3: недавние коммиты и изменённые файлы)
{git_context}

### Покрытие тестами (A4)
{coverage_context}

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

### Git (A3: недавние коммиты и изменённые файлы)
{git_context}

### Покрытие тестами (A4)
{coverage_context}

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

### Git (A3: недавние коммиты и изменённые файлы)
{git_context}

### Покрытие тестами (A4)
{coverage_context}

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
