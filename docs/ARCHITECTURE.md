# Архитектура TAI

Краткое описание слоёв и потоков данных.

## Слои

| Слой | Назначение | Примеры |
|------|------------|---------|
| **API** | Маршрутизация, валидация запросов, DI | `src/api/routes/`, `container.py`, `dependencies.py` |
| **Application** | Use Cases, оркестрация | `ChatUseCase`, `AgentUseCase`, `WorkflowUseCase`, `SelfImprovementUseCase` |
| **Domain** | Сущности, порты (интерфейсы), сервисы | `LLMPort`, `RAGPort`, `ModelSelector`, `IntentDetector` |
| **Infrastructure** | Адаптеры к внешним сервисам | Ollama, LM Studio (OpenAI-compatible), ChromaDB, agents (planner, coder, researcher) |

Зависимости направлены внутрь: API → Application → Domain; Infrastructure реализует порты Domain.

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

## Конфигурация

- `config/default.toml` + `config/development.toml`, переменные окружения (см. `.env.example`).
- Выбор провайдера LLM: `[llm] provider = "ollama"` или `"lm_studio"`.
- Модели по сложности задаются в `[models]` и `[models.lm_studio]`.

## Тесты

- `tests/` — интеграционные и unit-тесты (pytest).
- Адаптеры и use cases покрыты unit-тестами с моками портов.
