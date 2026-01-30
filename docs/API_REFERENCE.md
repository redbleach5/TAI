# API Reference

Документация по REST API CodeGen AI.

**Base URL:** `http://localhost:8000`

---

## Health

### GET /health

Проверка состояния сервиса и LLM backend.

**Response:**

```json
{
  "status": "ok",
  "service": "codegen-ai",
  "llm_provider": "ollama",
  "llm_available": true
}
```

---

## Chat

### POST /chat

Синхронный чат с LLM.

**Request:**

```json
{
  "message": "Объясни что такое рекурсия",
  "history": [
    {"role": "user", "content": "Привет"},
    {"role": "assistant", "content": "Привет! Чем могу помочь?"}
  ],
  "conversation_id": "optional-uuid"
}
```

**Response:**

```json
{
  "content": "Рекурсия — это...",
  "model": "qwen2.5-coder:7b",
  "conversation_id": "uuid"
}
```

### GET /chat/stream

Стриминговый чат через SSE.

**Query Parameters:**
- `message` (required): Сообщение пользователя
- `conversation_id` (optional): ID диалога

**SSE Events:**
- `content`: Текст ответа (чанки)
- `thinking`: Рассуждения модели (для reasoning-моделей)
- `done`: Завершение

---

## Workflow

### POST /workflow

Запуск TDD workflow: plan → tests → code → validation.

**Request:**

```json
{
  "task": "Напиши функцию факториала",
  "session_id": "optional-uuid"
}
```

**Response:**

```json
{
  "session_id": "uuid",
  "content": "...",
  "intent_kind": "code",
  "plan": "Step 1: ...",
  "tests": "def test_factorial(): ...",
  "code": "def factorial(n): ...",
  "validation_passed": true,
  "validation_output": "1 passed"
}
```

### POST /workflow?stream=true

Стриминговый workflow через SSE.

**SSE Events:**
- `plan`: Чанки плана
- `plan_thinking`: Рассуждения при планировании
- `tests`: Чанки тестов
- `tests_thinking`: Рассуждения при генерации тестов
- `code`: Чанки кода
- `code_thinking`: Рассуждения при генерации кода
- `done`: Финальный результат с payload
- `error`: Ошибка

---

## Code Execution

### POST /code/run

Выполнение Python кода в изолированном subprocess.

**Request:**

```json
{
  "code": "def add(a, b):\n    return a + b\n\nprint(add(1, 2))",
  "tests": "def test_add():\n    assert add(1, 2) == 3",
  "timeout": 30
}
```

**Response:**

```json
{
  "success": true,
  "output": "3\n===== 1 passed =====",
  "error": null
}
```

---

## Models

### GET /models

Список доступных моделей от текущего LLM provider.

**Response:**

```json
["qwen2.5-coder:7b", "qwen2.5-coder:32b", "nomic-embed-text"]
```

---

## Config

### GET /config

Получение редактируемых настроек.

**Response:**

```json
{
  "llm": {"provider": "ollama"},
  "models": {
    "defaults": {"simple": "qwen2.5-coder:7b", "medium": "...", "complex": "...", "fallback": "..."},
    "lm_studio": {"simple": "local", "medium": "local", "complex": "local", "fallback": "local"}
  },
  "embeddings": {"model": "nomic-embed-text"},
  "logging": {"level": "INFO"}
}
```

### PATCH /config

Обновление настроек. Сохраняется в `config/development.toml`.

**Request:**

```json
{
  "llm": {"provider": "lm_studio"},
  "logging": {"level": "DEBUG"}
}
```

**Response:**

```json
{
  "ok": true,
  "message": "Config saved. Restart backend to apply changes."
}
```

---

## RAG

### POST /rag/index

Индексация директории для RAG поиска.

**Query Parameters:**
- `path` (required): Путь к директории

**Response:**

```json
{"status": "indexed", "path": "."}
```

### GET /rag/status

Статус RAG индекса.

**Response:**

```json
{
  "status": "ready",
  "documents": 42,
  "collection": "codebase"
}
```

---

## Conversations

### GET /conversations

Список сохранённых диалогов.

**Response:**

```json
[
  {"id": "uuid-1", "created_at": "2026-01-30T12:00:00Z"},
  {"id": "uuid-2", "created_at": "2026-01-30T13:00:00Z"}
]
```

### GET /conversations/{id}

Загрузка диалога по ID.

**Response:**

```json
{
  "id": "uuid",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

---

## Self-Improvement

### POST /improve/analyze

Анализ проекта на проблемы и предложение улучшений.

**Request:**

```json
{
  "path": "src",
  "include_linter": true,
  "use_llm": false
}
```

**Response:**

```json
{
  "total_files": 42,
  "total_lines": 3500,
  "total_functions": 120,
  "total_classes": 25,
  "avg_complexity": 4.2,
  "issues": [
    {
      "file": "src/module.py",
      "line": 42,
      "type": "complexity",
      "severity": "medium",
      "message": "Function 'process' has high complexity (12)",
      "suggestion": "Consider breaking into smaller functions"
    }
  ],
  "suggestions": [
    {
      "priority": 1,
      "title": "Fix Critical Issues",
      "description": "Found 2 critical issues",
      "estimated_effort": "high"
    }
  ]
}
```

### POST /improve/run

Запуск улучшения файла с автоматическим retry.

**Request:**

```json
{
  "file_path": "src/module.py",
  "issue": {
    "message": "Function has high complexity",
    "severity": "medium",
    "issue_type": "complexity"
  },
  "auto_write": true,
  "max_retries": 3
}
```

**Response:**

```json
{
  "success": true,
  "file_path": "src/module.py",
  "backup_path": "output/backups/module.py.20260130_123456.bak",
  "validation_output": "Syntax check passed",
  "error": null,
  "retries": 0
}
```

### Task Queue

Endpoints для управления очередью задач:

| Endpoint | Описание |
|----------|----------|
| `POST /improve/queue/add` | Добавить задачу в очередь |
| `GET /improve/queue/status` | Статус очереди |
| `GET /improve/queue/task/{id}` | Статус конкретной задачи |
| `POST /improve/queue/start` | Запустить worker |
| `POST /improve/queue/stop` | Остановить worker |
| `POST /improve/queue/clear` | Очистить завершённые |

---

## Files

### POST /files/write

Запись файла с автоматическим backup.

**Request:**

```json
{
  "path": "src/module.py",
  "content": "# New content",
  "create_backup": true
}
```

**Response:**

```json
{
  "success": true,
  "path": "/full/path/src/module.py",
  "backup_path": "output/backups/module.py.20260130_123456.bak",
  "created": false,
  "error": null
}
```

### GET /files/read?path=src/module.py

Чтение файла.

### GET /files/backups

Список доступных backup-ов.

### POST /files/restore

Восстановление из backup.

---

## Error Responses

Все ошибки возвращают JSON:

```json
{
  "detail": "Error message"
}
```

**HTTP Codes:**
- `400` - Bad Request
- `404` - Not Found
- `429` - Too Many Requests (rate limit)
- `500` - Internal Server Error
