Полная инкрементальная индексация! ✓ Реализовано 2026-01-31

**Реализовано:**
- IndexState — отслеживание проиндексированных файлов (mtime, size) в JSON
- collect_code_files_with_stats — сбор файлов с метаданными
- ChromaDB: index_path(incremental=True) — только новые/изменённые файлы
- delete_chunks_by_source — удаление чанков при изменении/удалении файла
- API: ?incremental=true (по умолчанию) для workspace, projects, rag
- Frontend: toast с деталями (+N новых, ~M изменённых, -K удалённых)



# План-промпт: Создание проекта с нуля (улучшенная архитектура)

**Цель:** Документ для создания аналога Cursor Killer с нуля — локальная многоагентная система генерации кода на LLM, но с более чистой, поддерживаемой и масштабируемой архитектурой.

**Обновлено:** 2026-01-30 — Phase 0–4 реализованы (RAG, embeddings, researcher node).

---

## 0. Старт с нуля: предварительные требования и первый запуск

### 0.1 Системные требования

| Компонент | Минимум | Рекомендуется | Проверка |
|-----------|---------|---------------|----------|
| **Python** | 3.11 | 3.12 или 3.13 | `python --version` |
| **Node.js** | 20 LTS | 22 LTS или 24 LTS | `node --version` |
| **LLM backend** | Ollama **или** LM Studio | один из двух | см. ниже |
| **Git** | 2.x | последняя | `git --version` |

**LLM backend (выбрать один):**
- **Ollama** — [ollama.com](https://ollama.com), `ollama --version`
- **LM Studio** — [lmstudio.ai](https://lmstudio.ai), GUI для загрузки моделей, OpenAI-совместимый API на `http://localhost:1234/v1`

**Установка:**
- Python: [python.org](https://www.python.org/downloads/) или `pyenv install 3.12`
- Node.js: [nodejs.org](https://nodejs.org/) (LTS)
- Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
- LM Studio: [lmstudio.ai](https://lmstudio.ai) — скачать, установить, загрузить модель, включить Local Server

### 0.2 Версии зависимостей (совместимый набор, 2026)

**Backend (Python):**
```
# pyproject.toml или requirements.in
python = ">=3.11,<3.14"

fastapi[standard]>=0.115,<0.130
uvicorn[standard]>=0.32
pydantic>=2.9,<3
sse-starlette>=3.2

langgraph>=1.0,<2.0
langchain-core>=0.3
ollama>=0.4              # для Ollama backend
chromadb>=0.5
httpx[http2]>=0.28       # для LM Studio, vLLM, LocalAI (OpenAI-совместимый API)

tomli-w>=1.0
structlog>=24.0
pytest>=8.0
pytest-asyncio>=0.24
ruff>=0.8
```

**Frontend:**
```
# package.json
"react": "^19.0.0"
"react-dom": "^19.0.0"
"typescript": "~5.7"
"vite": "^6.0"
"@vitejs/plugin-react": "^4.3"
```

### 0.3 Шаг 0: создание проекта

```bash
# 1. Создать директорию и инициализировать
mkdir codegen-ai && cd codegen-ai
git init

# 2. Backend: pyproject.toml
cat > pyproject.toml << 'EOF'
[project]
name = "codegen-ai"
version = "0.1.0"
requires-python = ">=3.11,<3.14"
dependencies = [
    "fastapi[standard]>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "sse-starlette>=3.2",
    "langgraph>=1.0",
    "ollama>=0.4",           # Ollama
    "httpx[http2]>=0.28",    # LM Studio, vLLM, LocalAI
    "tomli-w>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "ruff>=0.8"]
EOF

# 3. Установить зависимости
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 4. Frontend
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install && cd ..

# 5. Базовая структура
mkdir -p src/api/routes src/application src/domain/ports src/infrastructure/llm
touch src/__init__.py src/main.py
touch src/infrastructure/llm/ollama.py src/infrastructure/llm/openai_compatible.py
```

### 0.4 Первый запуск (минимальный API)

```python
# src/main.py
from fastapi import FastAPI

app = FastAPI(title="CodeGen AI", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "codegen-ai"}

# Запуск: uvicorn src.main:app --reload --port 8000
```

```bash
# Проверка
uvicorn src.main:app --reload --port 8000
# В другом терминале:
curl http://localhost:8000/health
```

**Расширенный health (Фаза 0):** endpoint должен проверять доступность LLM и возвращать `llm_provider: "ollama" | "lm_studio"` и `llm_available: true/false`.

### 0.5 Проверка LLM backend

**Ollama:**
```bash
ollama serve   # если не запущен
ollama pull qwen2.5-coder:7b   # или phi3:mini для быстрого старта
curl http://localhost:11434/api/tags   # список моделей
```

**LM Studio:**
1. Запустить LM Studio
2. Загрузить модель (например, Qwen2.5-Coder-7B-Instruct)
3. Включить Local Server (иконка слева)
4. Проверка: `curl http://localhost:1234/v1/models`

### 0.6 Сравнение API: Ollama vs LM Studio

| Действие | Ollama | LM Studio |
|----------|--------|-----------|
| Chat | `POST /api/chat` | `POST /v1/chat/completions` |
| Список моделей | `GET /api/tags` | `GET /v1/models` |
| Embeddings | `POST /api/embeddings` | `POST /v1/embeddings` |
| Порт по умолчанию | 11434 | 1234 |
| Формат ответа | Собственный | OpenAI-совместимый |

Оба backend поддерживают chat и embeddings; Model Router и RAG должны работать с любым из них.

---

## 1. Видение проекта

### Что строим

**Локальная AI-система для генерации кода** — альтернатива Cursor AI, работающая на собственной инфраструктуре (Ollama, LM Studio) без облачных API.

**Ключевые возможности:**
- Режимы: chat (диалог), code (TDD workflow с генерацией кода)
- Умный выбор моделей по сложности задачи (SIMPLE/MEDIUM/COMPLEX)
- Real-time стриминг (thinking + code)
- Встроенная IDE для просмотра и редактирования сгенерированного кода
- RAG по кодовой базе, веб-поиск, Hugging Face Hub
- Поддержка reasoning-моделей (DeepSeek-R1, QwQ) с `<think>` блоками

**Целевая аудитория:** Разработчики, предпочитающие локальные LLM и контроль над данными.

---

## 2. Уроки из текущего проекта (что сохранить / что изменить)

### ✅ Сохранить

| Аспект | Почему |
|--------|--------|
| LangGraph для workflow | Чёткая визуализация графа, checkpointing, условные переходы |
| Ollama + LM Studio | Два backend через LLMPort, переключение в config |
| ModelRouter (config-driven) | Выбор модели по сложности; per-provider overrides без хардкода |
| SSE для стриминга | Простой, надёжный, работает везде |
| config.toml + env | Гибкая конфигурация без пересборки |
| Structured Output (Pydantic) | Стабильный парсинг ответов LLM |
| EventStore для событий | State не раздувается, изоляция по сессии |
| Connection pool (Ollama) / httpx.Client (LM Studio) | Эффективная работа с локальным или удалённым LLM |

### ❌ Изменить / избежать

| Проблема | Решение |
|----------|---------|
| **Дублирование sync/stream агентов** | Один агент с опциональным стримингом через Protocol/Adapter |
| **Разбросанная конфигурация** | Единый Config-класс, схема валидации при старте |
| **Устаревший кэш при недоступности** | Проверка доступности перед возвратом кэша, fail-fast |
| **Монолитный agent.py (1700+ строк)** | Разделение на handlers по режимам с самого начала |
| **Смешение RU/EN в промптах** | Единый язык (EN) для structured, RU только в user-facing |
| **Нет слоя домена** | Чёткий domain layer между API и infrastructure |
| **Тесты зависят от моков** | Контракты (Protocol), внедрение зависимостей |
| **config.toml 500+ строк** | Группировка, опциональные секции, defaults в коде |
| **Два набора агентов** (sync + stream) | Один агент с callback — ~70% дублирования в текущем проекте |
| **Intent через LLM** для простых запросов | Эвристика для greeting; LLM только для пограничных случаев |
| **Суммаризация через LLM** при overflow | Sliding window или truncate; суммаризация — Фаза 6 |

---

## 3. Архитектурные принципы

### 3.1 Слои (сверху вниз)

```
┌─────────────────────────────────────────────────────────┐
│  Presentation (API, SSE, WebSocket)                      │
│  - Только маршрутизация, валидация входа, формат ответа │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Application (Use Cases)                                 │
│  - ChatUseCase, WorkflowUseCase, AnalyzeUseCase         │
│  - Оркестрация, не содержит бизнес-логики               │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Domain                                                  │
│  - Entities: Task, Conversation, ModelSelection         │
│  - Ports: LLMPort, RAGPort, EmbeddingsPort, ConfigPort   │
│  - Без зависимостей от framework/infrastructure         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Infrastructure (Adapters)                               │
│  - OllamaAdapter, OpenAICompatibleAdapter, ChromaDB,    │
│    OllamaEmbeddingsAdapter, OpenAIEmbeddingsAdapter     │
│  - Реализует Ports из domain                            │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Ключевые правила

1. **Dependency Inversion:** Domain определяет интерфейсы (Ports), Infrastructure их реализует.
2. **Один вход в use case:** Каждый use case — одна точка входа, одна ответственность.
3. **Явные контракты:** Protocol/ABC для всех внешних зависимостей.
4. **Fail-fast:** При старте проверять доступность выбранного LLM (Ollama или LM Studio); перед возвратом кэша — актуальность.
5. **Observability first:** Structured logging, метрики, трейсинг с первого дня.

---

## 4. Предлагаемая структура проекта

```
project/
├── src/
│   ├── api/                    # Presentation
│   │   ├── routes/
│   │   │   ├── chat.py
│   │   │   ├── workflow.py
│   │   │   ├── models.py
│   │   │   └── config.py
│   │   ├── middleware/
│   │   ├── sse/
│   │   └── dependencies.py     # FastAPI Depends
│   │
│   ├── application/           # Use Cases
│   │   ├── chat/
│   │   │   ├── use_case.py
│   │   │   └── dto.py
│   │   ├── workflow/
│   │   │   ├── use_case.py
│   │   │   └── dto.py
│   │   └── analyze/
│   │       └── use_case.py
│   │
│   ├── domain/                # Core
│   │   ├── entities/
│   │   │   ├── task.py
│   │   │   ├── conversation.py
│   │   │   └── model_selection.py
│   │   ├── ports/             # Interfaces (Protocol)
│   │   │   ├── llm.py
│   │   │   ├── rag.py
│   │   │   ├── config.py
│   │   │   └── event_bus.py
│   │   └── services/          # Domain logic
│   │       ├── intent_detector.py
│   │       └── model_router.py
│   │
│   ├── infrastructure/       # Adapters
│   │   ├── llm/
│   │   │   ├── ollama.py           # OllamaAdapter
│   │   │   ├── openai_compatible.py # LM Studio, vLLM, LocalAI (httpx → /v1/chat/completions)
│   │   │   └── connection_pool.py  # для Ollama; httpx.Client — для LM Studio
│   │   ├── rag/
│   │   │   └── chromadb.py
│   │   ├── web_search.py        # Веб-поиск (опционально)
│   │   ├── workflow/
│   │   │   ├── graph.py
│   │   │   └── nodes/
│   │   ├── agents/            # Реализации агентов (вызывают LLM через port)
│   │   │   ├── intent.py
│   │   │   ├── chat.py
│   │   │   ├── planner.py
│   │   │   ├── coder.py
│   │   │   └── ...
│   │   └── config/
│   │       └── toml_loader.py
│   │
│   └── shared/
│       ├── logging/
│       ├── errors/
│       └── types/
│
├── frontend/                  # React + TypeScript + Vite
│   └── src/
│       ├── features/          # По фичам, не по типам компонентов
│       │   ├── chat/
│       │   ├── workflow/
│       │   ├── ide/
│       │   └── settings/
│       ├── shared/
│       └── api/
│
├── config/
│   ├── default.toml           # Defaults
│   ├── development.toml       # Overrides для dev
│   └── schema.json            # JSON Schema для валидации
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   └── application/
│   ├── integration/
│   │   └── infrastructure/
│   └── e2e/
│
└── docs/
```

### 4.1 Config: выбор LLM backend и моделей

**Принцип:** Config-driven, без хардкода провайдеров в коде. Добавление нового провайдера — только через конфиг.

```toml
# config/default.toml
[llm]
provider = "ollama"   # или "lm_studio"

[ollama]
host = "http://localhost:11434"

[openai_compatible]
base_url = "http://localhost:1234/v1"

# Model Router: defaults для Ollama + per-provider overrides
# Сложность задачи (SIMPLE/MEDIUM/COMPLEX) определяется эвристикой — одинаково для всех провайдеров
# Имена моделей зависят от provider — задаются в [models.<provider>]
[models]
simple = "qwen2.5-coder:7b"
medium = "qwen2.5-coder:7b"
complex = "qwen2.5-coder:32b"
fallback = "qwen2.5-coder:7b"

# Per-provider overrides. Добавить [models.<provider>] для любого провайдера.
# LM Studio: "local" = загруженная модель; или точный ID из GET /v1/models
[models.lm_studio]
simple = "local"
medium = "local"
complex = "local"
fallback = "local"

[embeddings]
provider = "auto"
model = "nomic-embed-text"
```

**Масштабируемость:** Новый провайдер (openai, groq и т.д.) — добавить `[models.openai]` в конфиг. ModelRouter использует `config.get_models_for_provider(provider)` — без проверок `if provider == ...` в коде.

### 4.2 Отличия от текущей структуры

- **Нет `agents/` на верхнем уровне** — агенты в `infrastructure/agents/`, т.к. это адаптеры к LLM.
- **Domain layer** — явные entities и ports, тестируемые без моков инфраструктуры.
- **Use cases** — тонкий слой оркестрации, легко тестировать.
- **Frontend по features** — `features/chat/`, `features/workflow/` вместо `components/chat/`, `components/ide/`.
- **Config schema** — JSON Schema для валидации при старте.

---

## 5. План реализации по фазам

### Фаза 0: Фундамент (1–2 недели)

1. **Структура проекта** — создать папки, pyproject.toml, базовые модули.
2. **Config** — загрузка TOML, валидация по схеме, env overrides.
3. **Logging** — structured JSON logs, уровни, контекст (request_id).
4. **Ports** — определить `LLMPort`, `ConfigPort`, `RAGPort` в domain.
5. **LLM adapters** — реализация LLMPort (оба адаптера с самого начала):
   - **OllamaAdapter** — ollama API, connection pool, `/api/chat`, `/api/tags`
   - **OpenAICompatibleAdapter** — LM Studio, vLLM, LocalAI (httpx, `/v1/chat/completions`, `/v1/models`)
6. **Config [llm]** — `provider = "ollama" | "lm_studio"`, секции `[ollama]` и `[openai_compatible]`.
7. **Health check** — `/health` возвращает `llm_provider`, `llm_available`, проверяет доступность выбранного backend.
8. **Security** — CORS, Rate Limiting (middleware); .env.example для env overrides.
9. **FastAPI lifespan** — инициализация connection pool при старте, graceful shutdown.

**Критерий готовности:** `python -m src` запускает приложение; `/health` возвращает статус выбранного backend (Ollama или LM Studio).

### Фаза 1: Chat режим (1 неделя)

1. **ChatUseCase** — принять message, вызвать LLM через port, вернуть response.
2. **IntentDetector** — эвристика по ключевым словам; greeting (1–2 слова) → chat без LLM; code-слова → workflow.
3. **API route** — POST /chat (sync) и GET /chat/stream (SSE).
4. **Frontend** — минимальный chat UI, SSE hook; layout: chat/ide/split.
5. **ConversationMemory** — сохранение диалогов в output/conversations/; sliding window или truncate (без LLM-суммаризации в MVP).

**Критерий:** Пользователь может отправить сообщение и получить ответ; greeting — быстрый ответ без workflow.

### Фаза 2: Model Router (1 неделя)

1. **ModelRouter** (domain service) — выбор модели по TaskComplexity. **Provider-agnostic:** использует `config.get_models_for_provider(provider)` — без хардкода имён провайдеров.
2. **Config-driven per-provider overrides** — `[models]` defaults + `[models.lm_studio]`, `[models.ollama]` и т.д. Добавление провайдера = новая секция в конфиге.
3. **Model scanner** — единый интерфейс: Ollama `GET /api/tags`, LM Studio `GET /v1/models`.
4. **Инвалидация кэша** — при недоступности backend не возвращать устаревший кэш; fail-fast.
5. **Интеграция** — ChatUseCase и workflow-агенты получают модель через router.

**Критерий:** Для SIMPLE/MEDIUM/COMPLEX выбираются разные модели; работает с Ollama и LM Studio; fallback при недоступности; новый провайдер добавляется только через конфиг.

### Фаза 3: Workflow (2–3 недели)

1. **Workflow graph** — LangGraph: intent → planner → researcher → tests → coder → validator → END. MVP без debugger/reflection/critic.
2. **Условные переходы** — `should_skip_greeting` (greeting/help → END).
3. **Агенты** — один стиль: `async (state, llm, model, on_chunk?) -> state`; стриминг через callback; без дублирования sync/stream.
4. **Retry** — tenacity для LLM (TimeoutError, ConnectionError); 2–3 попытки.
5. **Checkpointing** — только LangGraph MemorySaver; события стримятся через callback, state минимальный.
6. **API** — `POST /workflow` (sync) и `POST /workflow?stream=true` (SSE).
7. **Frontend** — вкладка Workflow, WorkflowPanel, useWorkflowStream; отображение plan/tests/code/validation.

**Критерий:** Полный TDD workflow выполняется; greeting → END без графа; код стримится в UI; ошибки отображаются пользователю.

### Фаза 4: RAG и контекст (1 неделя) ✓

1. **RAGPort** — интерфейс: `search(query, limit) -> List[Chunk]`, `index_path(path)`.
2. **EmbeddingsPort** — OllamaEmbeddingsAdapter, OpenAICompatibleEmbeddingsAdapter.
3. **ChromaDB adapter** — индексация .py файлов, similarity search.
4. **Researcher node** — RAG search по task+plan, передаёт context в tests_writer и coder.
5. **API** — `POST /rag/index?path=.`, `GET /rag/status`.

**Критерий:** Workflow использует релевантные фрагменты кода из проекта; embeddings работают с выбранным backend.

### Фаза 5: IDE и артефакты (1 неделя)

1. **File management** — сохранение сгенерированного кода, табы.
2. **Frontend IDE** — редактор с подсветкой, кнопки Copy/Download; layout chat/ide/split.
3. **Выполнение кода** — subprocess с таймаутом и изоляцией; или «Copy to run locally» без выполнения в MVP.
4. **Project indexing** — API для индексации папки, статус.

**Критерий:** Пользователь видит код в IDE, может скопировать; выполнение — с subprocess или отложено.

### Фаза 6: Reasoning, интеграции, полировка (2 недели)

1. **Reasoning models** — парсинг `<think>`, стриминг thinking в UI.
2. **Hugging Face, n8n** — опциональные адаптеры, config-driven.
3. **Settings UI** — редактор config через API.
4. **Опционально:** Circuit Breaker, LLM-суммаризация контекста, incremental coding.
5. **Документация** — README, ARCHITECTURE, CONTRIBUTING.

---

## 6. Технологический стек

| Компонент | Выбор | Версия (2026) | Обоснование |
|-----------|-------|---------------|-------------|
| Backend | FastAPI | 0.115+ | Async, Pydantic v2, OpenAPI |
| Workflow | LangGraph | 1.0+ | Граф, checkpointing, Python 3.10+ |
| LLM (Ollama) | ollama | 0.4+ | Локальный, простой API, connection pool |
| LLM (LM Studio) | httpx | 0.28+ | OpenAI-совместимый API, vLLM/LocalAI тоже |
| RAG | ChromaDB | 0.5+ | Embeddings: Ollama или LM Studio (оба поддерживают) |
| Frontend | React + TypeScript + Vite | React 19, Vite 6 | Быстрая сборка, типизация |
| Config | TOML + Pydantic | tomli-w 1.0+ | Читаемость, валидация |
| Logging | structlog | 24.0+ | Structured JSON logs |
| Tests | pytest + pytest-asyncio | 8.0+, 0.24+ | Стандарт для Python |
| Linter | ruff | 0.8+ | Быстрый, заменяет flake8+isort |

---

## 7. Антипаттерны (чего избегать)

1. **Глобальный singleton без DI** — передавать зависимости явно или через FastAPI Depends.
2. **Кэш без проверки актуальности** — перед возвратом кэша проверять доступность источника.
3. **Смешение sync и async** — предпочитать async везде, sync только для блокирующих вызовов через `asyncio.to_thread`.
4. **Магические строки** — константы, enum для режимов, этапов, типов событий.
5. **Промпты в коде** — вынести в файлы (YAML/JSON) или отдельный модуль `prompts/`.
6. **Игнорирование ошибок** — логировать, пробрасывать или оборачивать в domain-ошибки.
7. **Роутер > 500 строк** — разбивать на handlers, выносить логику в use cases.

### 7.1 НЕ тащить из текущего проекта

| Проблема | Почему не тащить | Вместо этого |
|----------|------------------|--------------|
| **Два набора агентов** (sync + stream) | ~70% дублирования кода | Один агент с callback для стриминга |
| **StreamingAgentsCache** с threading.Lock | Сложность, race conditions | Один агент на тип, без кэша по модели |
| **Intent через LLM** для простых запросов | 3 прохода LLM для «напиши факториал» — избыточно | Эвристика + LLM только для пограничных случаев |
| **Суммаризация через LLM** | Дорого, задержка при каждом overflow | Sliding window или truncate; суммаризация — Фаза 6 |
| **NodeInputValidator** на каждый узел | Слишком строгая валидация блокирует выполнение | Корректная схема state, опциональная проверка |
| **Code Security** через regex (import os, requests) | Блокирует легитимный код | subprocess с таймаутом; или «Copy to run locally» без выполнения |
| **Circuit Breaker** в каждом узле | Усложняет отладку, прерывает при проблемах | Retry для transient errors; Circuit Breaker — опционально в Фазе 6 |
| **TaskCheckpointer** + LangGraph checkpointing | Дублирование механизмов | Только LangGraph checkpointing |
| **WorkflowConfig** с 20+ полями | Разбросанная конфигурация | Минимальный config, defaults в коде |
| **Разные таймауты по этапам** | Сложность, трудно отлаживать | Один общий timeout или 2–3 уровня |

---

## 8. Критерии успеха

- [ ] **Чистая архитектура:** Domain не импортирует из infrastructure.
- [ ] **Тестируемость:** Unit-тесты domain/application без реального Ollama/LM Studio.
- [ ] **Fail-fast:** При недоступности Ollama/LM Studio — понятная ошибка, без зацикливания.
- [ ] **Конфигурируемость:** Все настройки через config, без хардкода.
- [ ] **Документированность:** ARCHITECTURE.md описывает слои и потоки данных.
- [ ] **Расширяемость:** Добавление нового агента = новый node + регистрация в графе; новый провайдер = секция в config, без правок кода.

---

## 9. Промпт для AI (копировать при старте)

```
Создай проект локальной AI-системы для генерации кода по спецификации в docs/GREENFIELD_PROJECT_PLAN.md.

Требования:
1. Следуй слоистой архитектуре: api → application → domain → infrastructure
2. Domain определяет Ports (Protocol), Infrastructure их реализует
3. Используй LangGraph для workflow, FastAPI для API, React+TS для frontend
4. Config из TOML с валидацией при старте
5. Fail-fast при недоступности LLM — не используй устаревший кэш
6. Один агент = один стиль (стриминг через callback), без дублирования sync/stream версий
7. LLMPort: OllamaAdapter + OpenAICompatibleAdapter (LM Studio, vLLM, LocalAI). Config [llm] provider = "ollama" | "lm_studio", секции [ollama] и [openai_compatible]
8. Model Router: единый scanner для Ollama (/api/tags) и LM Studio (/v1/models)
9. См. раздел 7.1 — что НЕ тащить; раздел 10 — эффективные паттерны (упрощённый intent, retry, EventStore, LangGraph checkpointing)

Начни с Фазы 0: структура, config, logging, оба LLM adapters, CORS, Rate Limiting. Избегай дублирования sync/stream агентов.
```

---

## 10. Эффективные паттерны (только лучшее)

Компоненты, которые **реально работают** и не создают проблем. Остальное — см. раздел 7.1.

### 10.1 Режимы и Intent (упрощённо)

| Аспект | Рекомендация |
|--------|--------------|
| **mode=auto** | Простая эвристика по ключевым словам; **без LLM** для простых запросов |
| **is_greeting_fast()** | 1–2 слова (привет, hello) → chat, без workflow — **достаточно** |
| **Ключевые слова** | code: напиши, создай, реализуй, исправ; остальное → chat |
| **Условный переход** | `should_skip_greeting` в графе → greeting/help → END |

**Не тащить:** LLM для intent на каждый запрос; калибровка confidence; сложные промпты.

### 10.2 Безопасность и устойчивость

| Компонент | Рекомендация |
|-----------|--------------|
| **CORS** | CORSMiddleware, origins из config — обязательно |
| **Rate Limiting** | Лимит запросов/мин — обязательно |
| **Retry** | LLMTimeoutError → 2–3 попытки с задержкой — просто и эффективно |
| **Code execution** | subprocess с таймаутом, изоляция; или «Copy to run locally» без выполнения в MVP |

**Не тащить:** Circuit Breaker (Фаза 6, опционально); regex-проверки кода (блокируют легитимный код).

### 10.3 Персистентность

| Компонент | Рекомендация |
|-----------|--------------|
| **ConversationMemory** | output/conversations/{id}.json — обязательно |
| **Контекст** | Sliding window (последние N сообщений) или truncate — **без LLM суммаризации** в MVP |
| **Checkpointing** | Только LangGraph встроенный — без кастомного TaskCheckpointer |

**Не тащить:** LLM-суммаризация при overflow (дорого); дублирование checkpoint-механизмов.

### 10.4 Frontend

| Аспект | Рекомендация |
|--------|--------------|
| **Layout** | chat / ide / split — синхронизация с mode |
| **ChatHistory** | Сайдбар: список диалогов, загрузка — обязательно |
| **.env.example** | Документация env overrides |

### 10.5 Инфраструктура workflow

| Компонент | Рекомендация |
|-----------|--------------|
| **FastAPI lifespan** | Инициализация connection pool, graceful shutdown — обязательно |
| **EventStore** | События вне state (session_id), TTL — state не раздувается |
| **Таймауты** | 1–2 уровня (короткий/длинный), не 10 разных по этапам |

**Не тащить:** NodeInputValidator на каждый узел; WorkflowConfig с 20 полями; incremental coding в Фазе 3.

### 10.6 Config (минимальный)

```toml
[security]
rate_limit_requests_per_minute = 100
cors_origins = ["http://localhost:5173"]

[persistence]
output_dir = "output"
max_context_messages = 20
```

### 10.7 Model Router — config-driven, provider-agnostic

| Аспект | Рекомендация |
|--------|--------------|
| **Per-provider overrides** | `[models]` defaults + `[models.lm_studio]`, `[models.ollama]` и т.д. |
| **Без хардкода провайдеров** | ModelRouter использует `config.get_models_for_provider(provider)` — никаких `if provider == "lm_studio"` |
| **Сложность задачи** | Эвристика по ключевым словам — одинакова для всех провайдеров |
| **Расширяемость** | Новый провайдер (openai, groq) — добавить `[models.openai]` в конфиг |

**Не тащить:** Хардкод имён провайдеров в ModelRouter; отдельные поля `lm_studio_model` вместо per-provider overrides.

---

## 11. Связанные документы

- [ARCHITECTURE.md](../../ARCHITECTURE.md) — текущая архитектура (референс)
- [future/SCALABILITY_AND_ARCHITECTURE_PLAN.md](../../future/SCALABILITY_AND_ARCHITECTURE_PLAN.md) — план масштабирования
- [future/QUALITY_IMPROVEMENT_PLAN.md](../../future/QUALITY_IMPROVEMENT_PLAN.md) — улучшения качества
