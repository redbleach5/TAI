# TAI (TAi)

Локальная AI-система для разработки — альтернатива Cursor AI, работающая на своей инфраструктуре (Ollama, LM Studio) без облачных API.

**Репозиторий:** [github.com/redbleach5/TAI](https://github.com/redbleach5/TAI)

## Возможности

- **Чат (Cursor-like)** — диалог с LLM; модель автоматически видит открытые файлы, текущий файл и (после индексации) структуру проекта и релевантный код. Команды @web, @code, @file, @rag опциональны.
- **Режим агента** — автономное выполнение: read_file, write_file, search_rag, run_terminal, list_files, get_index_status, index_workspace. Предложенные изменения файлов можно **применить или отклонить** в чате (как в Cursor).
- **Ollama и LM Studio** — оба провайдера; с LM Studio поддерживаются нативные tool calls (Qwen, Llama 3.1+ и др.).
- **Workflow** — TDD: intent → planner → researcher (RAG) → tests → coder → validator.
- **RAG** — ChromaDB + embeddings; индексация через UI или API; auto-RAG в чате; project map в контексте.
- **Multi-Project** — несколько проектов, переключение workspace.
- **Режимы ассистента** — Coder, Researcher, Writer, Analyst, Reviewer и др.
- **Self-Improvement** — анализ проекта, улучшение кода с retry loop.
- **IDE** — File Browser, Multi-File Editor (Monaco), Terminal, Git.
- **Анализ проекта** — безопасность, качество, архитектура, Markdown-отчёты.
- **Reasoning** — парсинг `<think>`, стриминг thinking в UI.
- **Settings UI** — редактирование config через веб-интерфейс.

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

### 4. Проект и RAG

1. В UI откройте папку проекта (кнопка «Открыть папку»).
2. Нажмите «Индексировать» для семантического поиска по коду (RAG). Либо в режиме агента попросите модель проиндексировать проект.

## API (основное)

| Endpoint | Описание |
|----------|----------|
| `GET /health` | Статус backend и LLM |
| `POST /chat` | Чат (sync) |
| `POST /chat/stream` | Чат (SSE, с context_files) |
| `GET /workspace` | Текущий workspace |
| `POST /workspace` | Открыть папку |
| `POST /workspace/index` | Индексация проекта для RAG |
| `GET /models` | Список моделей провайдера |
| `GET /conversations` | Список диалогов |
| `GET /config`, `PATCH /config` | Настройки |
| `POST /files/read`, `POST /files/write` | Чтение/запись файлов |
| `GET /files/tree` | Дерево файлов |
| `POST /improve/analyze`, `POST /improve/run` | Анализ и улучшение кода |
| `POST /analyze/project` | Полный анализ проекта |
| `POST /workflow` | Workflow (генерация кода) |

Полный список: http://localhost:8000/docs

## Конфигурация

- `config/default.toml` — базовые настройки
- `config/development.toml` — переопределения для dev
- Переменные окружения: см. `.env.example`

| Секция | Описание |
|--------|----------|
| `[llm] provider` | `ollama` \| `lm_studio` |
| `[models]` | Модели по сложности (defaults для Ollama) |
| `[models.lm_studio]` | Overrides для LM Studio |
| `[embeddings] model` | Модель для RAG |
| `[rag]` | ChromaDB path, chunk_size, chunk_overlap |

## Структура проекта

```
├── src/
│   ├── api/              # Routes, dependencies, container
│   ├── application/      # ChatUseCase, AgentUseCase, WorkflowUseCase, Improvement
│   ├── domain/           # Entities, Ports (LLMPort, RAGPort), Services
│   ├── infrastructure/   # Ollama, LM Studio, ChromaDB, agents
│   └── shared/
├── frontend/             # React + TypeScript + Vite
├── config/               # TOML
├── docs/                 # Документация
└── tests/
```

## Документация

- [CONTRIBUTING.md](CONTRIBUTING.md) — как внести вклад
- [docs/ROADMAP.md](docs/ROADMAP.md) — план развития (единый документ)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура
- [docs/README.md](docs/README.md) — индекс всей документации
- [docs/CHECKLIST.md](docs/CHECKLIST.md) — чеклист ручной проверки

## Лицензия

См. репозиторий.
