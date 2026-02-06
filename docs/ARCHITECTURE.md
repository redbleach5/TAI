# Архитектура TAI

Краткое описание слоёв, потоков данных и инженерных решений.

## Слои

| Слой | Назначение | Примеры |
|------|------------|---------|
| **API** | Маршрутизация, валидация запросов, DI | `src/api/routes/`, `container.py`, `dependencies.py` |
| **Application** | Use Cases, оркестрация | `ChatUseCase`, `AgentUseCase`, `WorkflowUseCase`, `SelfImprovementUseCase` |
| **Domain** | Сущности, порты (интерфейсы), сервисы | `LLMPort`, `RAGPort`, `ModelSelector`, `IntentDetector` |
| **Infrastructure** | Адаптеры к внешним сервисам | Ollama, LM Studio (OpenAI-compatible), ChromaDB, agents (planner, coder, researcher) |
| **Shared** | Кросс-слойные утилиты | Структурированное логирование (`structlog`), ротация логов |

Зависимости направлены внутрь: API → Application → Domain; Infrastructure реализует порты Domain.

## Dependency Injection

Singleton-контейнер `Container` (`src/api/container.py`) с ленивой инициализацией через `@cached_property`:

- **LLM**: `OllamaAdapter` или `OpenAICompatibleAdapter` (по `config.llm.provider`)
- **Embeddings**: `OllamaEmbeddingsAdapter` или `OpenAICompatibleEmbeddingsAdapter`
- **RAG**: `ChromaDBRAGAdapter` (ChromaDB + embeddings)
- **Model Router/Selector**: Выбор модели по сложности задачи
- **Use Cases**: `ChatUseCase`, `AgentUseCase`, `WorkflowUseCase`, `SelfImprovementUseCase`
- **Сервисы**: `FileService`, `GitService`, `TerminalService`, `PromptLibrary`

FastAPI-зависимости (`src/api/dependencies.py`) проксируют доступ к контейнеру через `Depends()`.

## Основные потоки

### Чат

1. Запрос приходит в `POST /chat` или `POST /chat/stream`.
2. `ChatUseCase` разрешает историю (conversation_id), обрабатывает команды (@rag, @code и т.д.), подмешивает context_files (открытые файлы), active_file_path, project map, auto-RAG.
3. Режим «agent» делегируется `AgentUseCase`: цикл LLM → tool_call → ToolExecutor (read_file, write_file, search_rag, index_workspace и др.) → Observation → LLM.
4. Ответ генерируется через `LLMPort` (Ollama или OpenAI-compatible для LM Studio).

### RAG и workspace

- Текущий проект хранится в projects store (`output/projects.json`).
- Индексация: `POST /workspace/index` или инструмент агента `index_workspace()` — ChromaDB индексирует файлы workspace, строится project map.
- В чат и агент подмешиваются релевантные чанки (auto-RAG или @rag) и карта структуры проекта.

### Workflow (TDD)

- Intent → Planner → Researcher (RAG) → Tests writer → Coder → Validator (LangGraph).
- Используется тот же `LLMPort` и `RAGPort`.

### Self-Improvement

- Анализ проекта → выбор файла → plan → code → validate → retry (с RAG-контекстом ошибки).
- `SelfImprovementUseCase` оркестрирует через `improvement_graph` (LangGraph).
- FileWriter создаёт бэкапы перед записью.

## Обработка ошибок

Стандартизированный подход во всех слоях:

- **API-роутеры**: `try/except` → `logger.exception()` → `HTTPException` с соответствующим кодом (400/404/500).
- **Application**: Логирование на входе (`logger.debug`) и при ошибках (`logger.warning`/`logger.error`).
- **Infrastructure**: Все `except Exception: pass` заменены на `except Exception: logger.warning(...)` с трассировкой.
- **LLM Fallback**: Общая утилита `generate_with_fallback()` / `stream_with_fallback()` (`src/application/shared/llm_fallback.py`) для последовательного перебора моделей.

## Валидация входных данных

Все Pydantic-модели запросов имеют ограничения:

- **Пути**: `min_length=1, max_length=1024`
- **Текстовые поля**: `max_length` (от 1 000 до 10 000 000 в зависимости от назначения)
- **Числовые параметры**: `ge`/`le` диапазоны (timeout, retries, limit, score)
- **Списки**: `max_length` ограничивает размер

## Логирование

- **Формат**: `structlog` (структурированное JSON/текст) + стандартный `logging` для модулей.
- **Ротация**: Настраиваемая через `[logging]` в config (макс. размер, количество бэкапов).
- **Покрытие**: Все слои (API, Application, Infrastructure) имеют `logger = logging.getLogger(__name__)`.
- **Стиль**: Lazy `%s`-форматирование (без f-string в вызовах логгера).

## Resilience

- **Circuit Breaker**: `CircuitBreaker` для вызовов LLM (предотвращает каскадные отказы).
- **Retry**: `tenacity` с экспоненциальным backoff для LLM-генерации и эмбеддингов.
- **LLM Fallback**: Автоматический перебор моделей при отказе.
- **Graceful Shutdown**: `main.py` lifespan закрывает HTTP-пул и LLM-клиент.

## Конфигурация

- `config/default.toml` + `config/development.toml`, переменные окружения.
- Выбор провайдера LLM: `[llm] provider = "ollama"` или `"lm_studio"`.
- Модели по сложности задаются в `[models]` и `[models.lm_studio]`.
- Невалидные env-переменные (PORT, RATE_LIMIT, AGENT_MAX_ITERATIONS) логируются как warning.

## Тесты

- `tests/unit/` — 181 unit-тест с моками портов (pytest + pytest-asyncio).
- Адаптеры, use cases, domain-сервисы, анализатор, RAG-адаптер покрыты тестами.
- Быстрый CI: `pytest -m "not slow"` (без обращений к реальному LLM).
- Линтер: `ruff check src/` — 0 ошибок.
