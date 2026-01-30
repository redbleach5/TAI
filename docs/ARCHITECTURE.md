# Архитектура CodeGen AI

**Обновлено:** 2026-01-30

## Слои

```
┌─────────────────────────────────────────────────────────┐
│  API (FastAPI) — routes, dependencies                    │
│  /health, /chat, /workflow, /models, /rag, /config,      │
│  /files, /terminal, /git, /improve                       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Application (Use Cases)                                  │
│  ChatUseCase, WorkflowUseCase                             │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Domain — Entities, Ports, Services                       │
│  LLMPort, RAGPort, EmbeddingsPort, ModelRouter, Intent   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Infrastructure (Adapters)                               │
│  Ollama, OpenAICompatible (LM Studio), ChromaDB, agents   │
└─────────────────────────────────────────────────────────┘
```

## Потоки данных

### Chat
```
POST /chat → ChatUseCase → IntentDetector → LLMPort (Ollama/LM Studio)
         → ConversationMemory (save)
```

### Workflow
```
POST /workflow → WorkflowUseCase → LangGraph:
  intent → planner → researcher (RAG) → tests → coder → validator → END
```

### RAG
```
POST /rag/index → ChromaDBRAGAdapter.index_path(path)
  → collect .py files → chunk → EmbeddingsPort.embed_batch → ChromaDB

Workflow researcher → RAGPort.search(task+plan) → chunks → context
  → tests_writer, coder получают context в промпте
```

### Reasoning (Phase 6)
```
LLM stream → reasoning_parser.parse_reasoning_chunk()
  → <think> blocks → thinking events
  → content blocks → content events

Chat/Workflow SSE → event_type: "plan_thinking" | "plan" | "tests_thinking" | ...
  → Frontend: WorkflowPanel/ChatMessage отображают thinking в <details>
```

### Config (Phase 6)
```
GET /config → editable subset (llm, models, embeddings, logging)
PATCH /config → merge into config/development.toml → cache clear
  → Settings UI: форма редактирования, сохранение
  → Перезапуск backend для применения
```

## Ключевые решения

| Решение | Реализация |
|---------|------------|
| **LLM** | LLMPort — OllamaAdapter, OpenAICompatibleAdapter |
| **Embeddings** | EmbeddingsPort — OllamaEmbeddingsAdapter, OpenAICompatibleEmbeddingsAdapter |
| **RAG** | RAGPort — ChromaDBRAGAdapter |
| **Модели** | ModelRouter + config per-provider overrides (без хардкода) |
| **Workflow** | LangGraph, MemorySaver, один агент = один файл, стриминг через callback |
| **Reasoning** | reasoning_parser — парсинг `<think>`, стриминг thinking в UI |
| **Config UI** | GET/PATCH /config, Settings panel, сохранение в development.toml |

## Конфигурация

- **Provider-agnostic** — добавление провайдера через `[models.<provider>]` в config
- **Embeddings** — через активный LLM provider (Ollama или LM Studio)
- **RAG** — ChromaDB в `output/chromadb`, коллекция `codebase`

## Файловая структура

```
src/
├── api/routes/        chat, workflow, models, rag, config, code, files, terminal, git, improve
├── application/
│   ├── chat/          use_case, dto
│   ├── workflow/      use_case, dto
│   └── improvement/   use_case, dto (self-improvement)
├── domain/
│   ├── entities/      workflow_state, model_selection, workflow_events
│   ├── ports/         llm, rag, embeddings, config
│   └── services/      intent_detector, model_router
├── infrastructure/
│   ├── agents/        planner, researcher, tests_writer, coder, validator, analyzer, file_writer
│   ├── embeddings/    ollama, openai_compatible
│   ├── llm/           ollama, openai_compatible, reasoning_parser
│   ├── rag/           chromadb_adapter
│   └── workflow/      graph, improvement_graph

frontend/src/features/
├── chat/              ChatPanel, ChatMessage, ChatInput
├── workflow/          WorkflowPanel, useWorkflowStream
├── ide/               IDEPanel (workflow results)
├── editor/            MultiFileEditor, EditorTabs, useOpenFiles
├── files/             FileBrowser, useFileTree
├── terminal/          TerminalPanel, useTerminal
├── git/               GitPanel, useGitStatus
├── improve/           ImprovementPanel
├── settings/          SettingsPanel
└── layout/            Layout (main navigation)
```

## Self-Improvement Flow

```
┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌───────┐
│ Analyze │ → │   Plan   │ → │   Code   │ → │ Validate │ → │ Write │
└─────────┘   └──────────┘   └──────────┘   └──────────┘   └───────┘
                                  ↑               │
                                  └───────────────┘
                                    retry (max 3)
```

**Компоненты:**
- **Analyzer** — статический анализ (AST, complexity) + LLM code review
- **FileWriter** — безопасная запись с автоматическим backup
- **ImprovementGraph** — LangGraph workflow с retry loop
- **TaskQueue** — фоновая очередь задач улучшения

## Advanced IDE (Phase 8)

```
┌─────────────────────────────────────────────────┐
│  Tabs: Chat | Workflow | IDE | Результат | ...  │
├────────────┬────────────────────────────────────┤
│   Files    │   File Tabs: main.py | utils.py   │
│   or Git   ├────────────────────────────────────┤
│  (sidebar) │                                    │
│            │         Monaco Editor              │
│            │                                    │
│            ├────────────────────────────────────┤
│            │         Terminal Panel             │
└────────────┴────────────────────────────────────┘
```

**API Routes:**
- `/files/tree` — дерево файлов (исключает `__pycache__`, `.git`, `node_modules`)
- `/files/create`, `/files/delete`, `/files/rename` — файловые операции
- `/terminal/exec`, `/terminal/stream` — выполнение команд
- `/git/status`, `/git/diff`, `/git/log`, `/git/commit`, `/git/branches`, `/git/checkout`

**Security:**
- Files: операции только внутри project directory
- Terminal: whitelist команд (`python`, `pip`, `npm`, `git`, `ls`, etc.)
- Terminal: блокировка опасных паттернов (`&&`, `|`, `>`, `$`)
- Git: read + commit, без push по умолчанию

**Frontend компоненты:**
- **FileBrowser** — дерево файлов с Git-статусом, контекстное меню
- **MultiFileEditor** — Monaco Editor с динамическими табами
- **TerminalPanel** — терминал с историей команд
- **GitPanel** — Source Control с diff-просмотром и commit

## Тестирование

```
tests/
├── test_*.py          API integration tests
└── unit/
    ├── domain/        intent_detector, model_router, workflow_events
    ├── infrastructure/ llm adapters, embeddings, rag, reasoning_parser, config
    └── application/   chat_use_case, workflow_use_case
```

**Покрытие:** 76%+ (без интеграционных тестов с реальным LLM)
