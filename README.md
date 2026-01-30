# CodeGen AI

Локальная AI-система для генерации кода — альтернатива Cursor AI, работающая на собственной инфраструктуре (Ollama, LM Studio) без облачных API.

## Возможности

- **Chat** — диалог с LLM, greeting/help без workflow
- **Workflow** — TDD: intent → planner → researcher (RAG) → tests → coder → validator
- **Model Router** — выбор модели по сложности задачи (config-driven, per-provider)
- **RAG** — ChromaDB + embeddings для контекста из кодовой базы (все типы файлов, gitignore)
- **Project Map** — автогенерация карты проекта при индексации
- **Multi-Project** — работа с несколькими проектами
- **Quick Commands** — @web, @code, @rag команды в чате (Cherry Studio стиль)
- **Assistant Modes** — пресеты (Coder, Researcher, Writer, Analyst, Reviewer)
- **Web Search** — DuckDuckGo интеграция через @web
- **Prompt Templates** — библиотека готовых промптов
- **Стриминг** — SSE для chat и workflow
- **Reasoning** — парсинг `<think>` (DeepSeek-R1, QwQ), стриминг thinking в UI
- **Settings UI** — редактирование config через веб-интерфейс
- **Self-Improvement** — автоматический анализ, рефакторинг и улучшение кода с retry loop
- **Advanced IDE** — File Browser, Multi-File Editor (Monaco), Terminal, Git integration
- **Полноценная IDE** — Monaco Editor с подсветкой синтаксиса, редактированием и выполнением кода
- **Полированный UI** — табы IDE, индикатор шагов workflow, markdown в чате, toast, responsive

## Требования

- Python 3.11+
- Node.js 20+
- **LLM backend** (один из):
  - [Ollama](https://ollama.com) — `ollama pull qwen2.5-coder:7b`, `ollama pull nomic-embed-text`
  - [LM Studio](https://lmstudio.ai) — загрузить модель, включить Local Server

## Быстрый старт

### 1. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Ollama (если используете)
ollama serve
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text   # для RAG

# LM Studio: загрузить модель, включить Local Server на :1234

uvicorn src.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Проверка

- API: http://localhost:8000/health
- Frontend: http://localhost:5173
- OpenAPI: http://localhost:8000/docs

### 4. RAG (опционально)

Индексация проекта для контекста в workflow:

```bash
curl -X POST "http://localhost:8000/rag/index?path=."
curl http://localhost:8000/rag/status
```

## API

| Endpoint | Описание |
|----------|----------|
| `GET /health` | Статус backend и LLM |
| `POST /chat` | Chat (sync) |
| `GET /chat/stream` | Chat (SSE) |
| `POST /workflow` | Workflow (sync) |
| `POST /workflow?stream=true` | Workflow (SSE) |
| `GET /models` | Список моделей провайдера |
| `GET /conversations` | Список диалогов |
| `GET /config` | Настройки (для Settings UI) |
| `PATCH /config` | Обновление настроек |
| `POST /code/run` | Выполнение кода (sandbox) |
| `POST /improve/analyze` | Анализ проекта (issues, suggestions) |
| `POST /improve/run` | Запуск улучшения файла |
| `GET /improve/queue/status` | Статус очереди улучшений |
| `POST /files/write` | Запись файла с backup |
| `GET /files/tree` | Дерево файлов проекта |
| `POST /files/create` | Создание файла/директории |
| `POST /terminal/exec` | Выполнение команды |
| `GET /git/status` | Git статус |
| `POST /git/commit` | Git commit |
| `POST /rag/index?path=.` | Индексация директории |
| `GET /rag/status` | Статус RAG индекса |
| `POST /rag/search` | Поиск по индексу |
| `GET /rag/project-map` | Карта проекта |
| `GET /projects` | Список проектов |
| `POST /projects` | Добавить проект |
| `POST /projects/{id}/index` | Индексировать проект |
| `GET /assistant/modes` | Список режимов ассистента |
| `GET /assistant/templates` | Список шаблонов промптов |
| `POST /assistant/search/web` | Веб-поиск (DuckDuckGo) |

## Конфигурация

- `config/default.toml` — базовые настройки
- `config/development.toml` — переопределения для dev
- Переменные окружения: см. `.env.example`

### Ключевые секции

| Секция | Описание |
|--------|----------|
| `[llm] provider` | `ollama` \| `lm_studio` |
| `[models]` | Модели по сложности (defaults для Ollama) |
| `[models.lm_studio]` | Overrides для LM Studio (`simple = "local"` и т.д.) |
| `[embeddings] model` | Модель для RAG (`nomic-embed-text`) |
| `[rag]` | ChromaDB path, chunk_size, chunk_overlap |

## Структура проекта

```
├── src/
│   ├── api/              # Routes, dependencies
│   ├── application/      # ChatUseCase, WorkflowUseCase
│   ├── domain/           # Entities, Ports (LLMPort, RAGPort, EmbeddingsPort)
│   ├── infrastructure/   # Ollama, LM Studio, ChromaDB, agents
│   └── shared/           # Logging
├── frontend/             # React + TypeScript + Vite
├── config/               # TOML
└── tests/
```

## План развития

См. [plan.md](plan.md) — фазы 0–6.

| Фаза | Статус | Описание |
|------|--------|----------|
| 0 | ✓ | Фундамент: Ollama + LM Studio, config, CORS, rate limit |
| 1 | ✓ | Chat: SSE, ConversationMemory, intent, layout |
| 2 | ✓ | Model Router: per-provider overrides, fallback |
| 3 | ✓ | Workflow: LangGraph, planner → researcher → tests → coder → validator |
| 4 | ✓ | RAG: ChromaDB, embeddings, researcher node |
| 5 | ✓ | IDE: код, Copy, Download, layout split |
| 6 | ✓ | Reasoning, Settings UI, документация |
| 7 | ✓ | Self-Improvement: анализ, рефакторинг с retry loop |
| 8 | ✓ | Advanced IDE: File Browser, Terminal, Git integration |
| 9 | ✓ | Smart Context: расширенный RAG, Project Map, Multi-Project |
| 10 | ✓ | Cherry Studio: @commands, modes, templates, web search |

## Проверка

См. [check.md](check.md) — чеклист для ручной проверки по фазам.

## Документация

- [plan.md](plan.md) — план реализации
- [check.md](check.md) — руководство по проверке
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура
- [docs/API_REFERENCE.md](docs/API_REFERENCE.md) — API reference
- [CONTRIBUTING.md](CONTRIBUTING.md) — руководство по внесению вклада
