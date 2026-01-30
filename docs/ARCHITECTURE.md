# Архитектура CodeGen AI

**Обновлено:** 2026-01-30

## Слои

```
┌─────────────────────────────────────────────────────────┐
│  API (FastAPI) — routes, dependencies                    │
│  /health, /chat, /workflow, /models, /rag, /config,      │
│  /conversations                                          │
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
├── api/routes/        chat, workflow, models, rag, config, code, files, improve
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
