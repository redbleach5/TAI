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

### GET /files/tree?path=.

Получить дерево файлов проекта.

**Query Parameters:**
- `path` - корневая директория (default: ".")
- `max_depth` - максимальная глубина (default: 10)

**Response:**

```json
{
  "success": true,
  "tree": {
    "name": "src",
    "path": "src",
    "type": "directory",
    "children": [
      {
        "name": "main.py",
        "path": "src/main.py",
        "type": "file",
        "size": 1234,
        "extension": "py"
      }
    ]
  }
}
```

**Исключаемые директории:** `__pycache__`, `.git`, `node_modules`, `.venv`, `dist`, `build`

### POST /files/create

Создать файл или директорию.

**Request:**

```json
{
  "path": "src/new_module.py",
  "is_directory": false
}
```

### DELETE /files/delete?path=src/old.py

Удалить файл или директорию.

**Query Parameters:**
- `create_backup` - создать backup перед удалением (default: true)

### POST /files/rename

Переименовать/переместить файл.

**Request:**

```json
{
  "old_path": "src/old_name.py",
  "new_path": "src/new_name.py"
}
```

---

## Terminal

### POST /terminal/exec

Выполнить команду в терминале.

**Request:**

```json
{
  "command": "python --version",
  "cwd": "src",
  "timeout": 30
}
```

**Response:**

```json
{
  "success": true,
  "command": "python --version",
  "stdout": "Python 3.11.0\n",
  "stderr": "",
  "exit_code": 0,
  "error": null
}
```

**Разрешённые команды:** `python`, `pip`, `pytest`, `npm`, `node`, `git`, `ls`, `cat`, `grep`, `echo`, `pwd`, `mkdir`, `rm`, `cp`, `mv`, `touch`

**Заблокированные паттерны:** `&&`, `||`, `;`, `|`, `>`, `<`, `` ` ``, `$`

### GET /terminal/stream

SSE-стриминг вывода команды.

**Query Parameters:**
- `command` - команда для выполнения
- `cwd` - рабочая директория
- `timeout` - таймаут в секундах

**SSE Events:**

```
data: {"type": "start", "command": "ls", "pid": 12345}
data: {"type": "stdout", "data": "file.txt\n"}
data: {"type": "stderr", "data": "warning...\n"}
data: {"type": "exit", "exit_code": 0}
data: {"type": "error", "data": "Timeout after 30s"}
```

---

## Git

### GET /git/status

Получить статус git репозитория.

**Response:**

```json
{
  "success": true,
  "branch": "main",
  "files": [
    {"path": "src/main.py", "status": "M", "staged": false},
    {"path": "new_file.py", "status": "?", "staged": false}
  ],
  "ahead": 0,
  "behind": 0
}
```

**Status codes:** `M` (modified), `A` (added), `D` (deleted), `?` (untracked), `R` (renamed), `U` (unmerged)

### GET /git/diff

Получить diff изменений.

**Query Parameters:**
- `path` - конкретный файл (optional)
- `staged` - показать staged изменения (default: false)

**Response:**

```json
{
  "success": true,
  "path": "src/main.py",
  "diff": "--- a/src/main.py\n+++ b/src/main.py\n..."
}
```

### GET /git/log

Получить историю коммитов.

**Query Parameters:**
- `limit` - количество записей (default: 20, max: 100)
- `path` - фильтр по файлу (optional)

**Response:**

```json
{
  "success": true,
  "entries": [
    {
      "hash": "abc123def456...",
      "short_hash": "abc123d",
      "author": "John Doe",
      "date": "2026-01-30 12:00:00 +0300",
      "message": "Add new feature"
    }
  ]
}
```

### POST /git/commit

Создать коммит.

**Request:**

```json
{
  "message": "Fix bug in module",
  "files": ["src/main.py"]
}
```

Если `files` не указан, будут закоммичены все изменения.

**Response:**

```json
{
  "success": true,
  "hash": "abc123d",
  "message": "Fix bug in module"
}
```

### GET /git/branches

Получить список веток.

**Response:**

```json
{
  "success": true,
  "current": "main",
  "branches": ["main", "feature/new-api"]
}
```

### POST /git/checkout

Переключиться на ветку.

**Request:**

```json
{
  "branch": "feature/new-api",
  "create": false
}
```

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
