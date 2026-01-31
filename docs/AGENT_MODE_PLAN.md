# План реализации агентского режима (Agent Mode)

## Цель
Режим Agent — автономный помощник, который может читать/писать файлы, искать по коду, запускать команды и итерировать до решения задачи.

## Подход: ReAct (Reasoning + Acting)
Используем prompt-based tool invocation — работает с любыми моделями (Ollama, LM Studio), без зависимости от native tool-calling.

Формат вызова инструмента в ответе LLM:
```
<tool_call>
{"tool": "read_file", "path": "src/main.py"}
</tool_call>
```

## Фазы реализации

### Phase 1: Agent Tools
- **agent_tools.py** — определения инструментов (read_file, write_file, search_rag, run_terminal, list_files)
- **tool_executor.py** — выполнение инструментов с workspace root
- Инструменты используют FileService, TerminalService, RAGPort

### Phase 2: Agent Use Case
- **AgentUseCase** — цикл: LLM → parse tool_call → execute → inject Observation → LLM (max 10 итераций)
- **tool_parser.py** — парсинг `<tool_call>...</tool_call>` из ответа LLM
- System prompt для Agent с описанием инструментов

### Phase 3: Интеграция в Chat
- ChatUseCase: при mode_id=="agent" делегирует в AgentUseCase
- API: тот же /chat/stream, передаём mode_id=agent
- SSE events: content, tool_call, tool_result, done

### Phase 4: Frontend
- Добавить режим "Агент" в assistant_modes.py и API
- ModeSelector: отображать Agent
- ChatPanel: показывать tool_call/tool_result в UI (опционально — toast или inline)

## Инструменты Agent

| Tool | Args | Описание |
|------|------|----------|
| read_file | path | Прочитать файл (относительно workspace) |
| write_file | path, content | Записать файл (с подтверждением в UI) |
| search_rag | query | Поиск по кодовой базе |
| run_terminal | command | Выполнить команду (whitelist) |
| list_files | path? | Список файлов в директории |

## Безопасность
- read_file/write_file: только в пределах workspace
- run_terminal: whitelist команд (как TerminalService)
- write_file: по умолчанию требует подтверждения (auto_apply=false)
