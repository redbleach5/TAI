# Анализ соответствия архитектуры обновлённому плану

**Дата:** 2026-01-30

---

## 1. Соответствует плану ✓

| Компонент | Статус |
|-----------|--------|
| Слои api → application → domain → infrastructure | ✓ |
| Domain Ports: LLMPort, ConfigPort, RAGPort | ✓ |
| ChatUseCase, IntentDetector | ✓ |
| OllamaAdapter (LLMPort) | ✓ |
| Config TOML + env overrides | ✓ |
| structlog, FastAPI lifespan | ✓ |
| POST /chat, ChatPanel | ✓ |
| Frontend: features/chat/, api/ | ✓ |
| Структура: application/chat/, domain/services/ | ✓ |

---

## 2. Расхождения и пробелы

### 2.1 Phase 0 — Фундамент

| Требование плана | Текущее состояние | Действие |
|------------------|-------------------|----------|
| **LLM provider choice** `[llm] provider = "ollama" \| "lm_studio"` | Только Ollama | Добавить config, factory |
| **OpenAICompatibleAdapter** (LM Studio, vLLM, LocalAI) | Отсутствует | Создать `openai_compatible.py` |
| **Health** возвращает `llm_provider`, `llm_available` | Возвращает `ollama` | Переименовать, добавить provider |
| **CORS** middleware | Отсутствует | Добавить CORSMiddleware |
| **Rate Limiting** | Отсутствует | Добавить middleware |
| **.env.example** | Отсутствует | Создать |
| **config/schema.json** | Отсутствует | Опционально |
| **connection_pool.py** для Ollama | Не реализован (ollama lib использует httpx) | Опционально |
| **Секции config** `[openai_compatible]`, `[security]`, `[persistence]` | Только [ollama], [server] | Расширить config |

### 2.2 Phase 1 — Chat режим

| Требование плана | Текущее состояние | Действие |
|------------------|-------------------|----------|
| **GET /chat/stream (SSE)** | Только POST /chat | Добавить SSE endpoint |
| **Intent: code-слова → workflow** | Только greeting/help | Добавить code detection, заглушка workflow |
| **ConversationMemory** (output/conversations/) | Отсутствует | Добавить сохранение диалогов |
| **Layout chat/ide/split** | Только chat | Добавить layout (ide — заглушка) |
| **Sliding window / truncate** | Нет | Добавить max_context_messages |

### 2.3 Структура (план vs текущая)

| План | Текущая | Действие |
|------|---------|----------|
| `infrastructure/llm/openai_compatible.py` | — | Создать |
| `api/middleware/` | — | Создать (CORS, rate limit) |
| `api/sse/` | — | Создать для Phase 1 |
| `domain/ports/event_bus.py` | — | Phase 3 |
| `domain/entities/task.py`, `conversation.py` | Пустые | Phase 3 |
| `infrastructure/rag/`, `workflow/`, `agents/` | — | Phase 3–4 |

### 2.4 Config (план vs текущая)

**План:**
```toml
[llm]
provider = "ollama"  # или "lm_studio"

[ollama]
host = "http://localhost:11434"

[openai_compatible]
base_url = "http://localhost:1234/v1"

[models]
simple = "phi3:mini"
medium = "qwen2.5-coder:7b"
complex = "qwen2.5-coder:32b"

[embeddings]
provider = "auto"
model = "nomic-embed-text"

[security]
rate_limit_requests_per_minute = 100
cors_origins = ["http://localhost:5173"]

[persistence]
output_dir = "output"
max_context_messages = 20
```

**Текущая:** [ollama], [ollama.models], [server], [logging] — нет [llm], [openai_compatible], [security], [persistence], [embeddings].

---

## 3. Рекомендуемый порядок доработок

1. **Phase 0 alignment** — Config, OpenAICompatibleAdapter, LLM factory, Health, CORS, Rate Limit, .env.example
2. **Phase 1 completion** — SSE stream, ConversationMemory, code-intent, layout
3. **Phase 2** — Model Router, scanner для обоих backend
