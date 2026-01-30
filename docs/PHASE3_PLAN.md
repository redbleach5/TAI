# Phase 3: Workflow — Детальный план реализации

**Критерий готовности:** Полный TDD workflow выполняется, код стримится в UI; greeting завершает без полного графа.

---

## Принципы (НЕ нарушать)

| Принцип | Реализация |
|---------|-------------|
| **Один агент = один файл** | planner.py, coder.py — НЕТ stream_planner.py, stream_coder.py |
| **Стриминг через callback** | Агент принимает `on_chunk: Callable[[str], None]`, вызывает при генерации |
| **Только LangGraph checkpointing** | НЕТ кастомного TaskCheckpointer |
| **1–2 уровня timeout** | Один общий или short/long — НЕ 10 разных по этапам |
| **EventStore вне state** | События по session_id, state не раздувается |
| **Domain не импортирует infrastructure** | Агенты в infrastructure/agents/, вызывают LLM через port |

---

## Структура графа (упрощённо для MVP)

```
START
  │
  ▼
intent ──────────────────────────────────────┐
  │                                           │
  │ should_skip_greeting? (greeting/help)    │
  │      YES ──────────────────────────────► END (template response)
  │      NO                                   │
  ▼                                           │
planner (план задачи)                          │
  │                                           │
  ▼                                           │
researcher (stub — Phase 4: RAG)              │
  │                                           │
  ▼                                           │
tests (генерирует тесты)                      │
  │                                           │
  ▼                                           │
coder (генерирует код)                        │
  │                                           │
  ▼                                           │
validator (проверка: тесты проходят?)         │
  │      YES ───────────────────────────────► END
  │      NO                                   │
  ▼                                           │
debugger (исправление) ──► coder (retry) ────┘
```

**MVP:** Упростить до intent → planner → tests → coder → validator. Researcher, debugger, reflection, critic — опционально или заглушки.

---

## Этапы реализации (порядок строгий)

### Этап 1: Domain — State и типы событий

**Файлы:**
- `src/domain/entities/workflow_state.py` — TypedDict WorkflowState
- `src/domain/entities/workflow_events.py` — enum EventType, типы событий

**WorkflowState (минимальный):**
```python
# Поля: task, intent, plan, tests, code, validation_result, 
# current_step, error, messages (история для контекста)
```

**EventType:**
```python
# plan, tests, code, validation, error, done
```

**Критерий:** Импорты работают, типы определены.

---

### Этап 2: Infrastructure — Агенты (один стиль)

**Файлы:**
- `src/infrastructure/agents/__init__.py`
- `src/infrastructure/agents/planner.py` — генерирует план
- `src/infrastructure/agents/tests_writer.py` — генерирует тесты
- `src/infrastructure/agents/coder.py` — генерирует код
- `src/infrastructure/agents/validator.py` — запускает тесты (subprocess или mock)

**Сигнатура агента:**
```python
async def planner_node(
    state: WorkflowState,
    llm: LLMPort,
    model: str,
    on_chunk: Callable[[str, str], None] | None = None,  # (event_type, chunk)
) -> WorkflowState:
    # Вызов llm.generate_stream с on_chunk callback
    # Обновить state["plan"]
    return state
```

**Retry:** Обёртка для LLM-вызовов — 2–3 попытки при timeout.

**Критерий:** Каждый агент unit-тестируется с mock LLM.

---

### Этап 3: LangGraph — Граф

**Файлы:**
- `src/infrastructure/workflow/graph.py` — построение графа
- `src/infrastructure/workflow/nodes/__init__.py`
- `src/infrastructure/workflow/nodes/intent_node.py` — intent + should_skip_greeting
- `src/infrastructure/workflow/nodes/planner_node.py` — обёртка над агентом
- и т.д.

**Условные переходы:**
- `should_skip_greeting(state) -> bool` — True если greeting/help
- Маршрут: intent → conditional → END | planner

**Checkpointing:** MemorySaver из LangGraph (встроенный).

**Критерий:** Граф собирается, выполняется на тестовом state (без реального LLM).

---

### Этап 4: Application — WorkflowUseCase

**Файлы:**
- `src/application/workflow/__init__.py`
- `src/application/workflow/use_case.py` — WorkflowUseCase
- `src/application/workflow/dto.py` — WorkflowRequest, WorkflowResponse

**WorkflowUseCase:**
- `execute(request) -> WorkflowResponse` — sync, полный результат
- `execute_stream(request) -> AsyncIterator[WorkflowEvent]` — стримит события

**Интеграция с IntentDetector:** При intent=code → WorkflowUseCase; иначе ChatUseCase.

**Критерий:** WorkflowUseCase вызывает граф, возвращает/стримит результат.

---

### Этап 5: EventStore (опционально для MVP)

**Файлы:**
- `src/infrastructure/events/event_store.py` — in-memory, session_id, TTL

**Или:** События стримятся напрямую в SSE без персистентного store (MVP).

**Критерий:** События доходят до клиента через SSE.

---

### Этап 6: API — Workflow routes

**Файлы:**
- `src/api/routes/workflow.py`

**Endpoints:**
- `POST /workflow` — запуск, возвращает session_id + sync result (или 202 Accepted)
- `GET /workflow/stream/{session_id}` — SSE стрим событий

**Или упрощённо:** `POST /workflow` с SSE response (stream в теле).

**Критерий:** curl/Postman может запустить workflow и получить SSE.

---

### Этап 7: Интеграция Chat ↔ Workflow

**Изменения:**
- `ChatUseCase` или роутинг: при `intent.kind == "code"` → вызвать WorkflowUseCase
- `POST /chat` с message "напиши функцию X" → роут в workflow

**Вариант:** Отдельный `POST /workflow` — пользователь явно выбирает режим. Или auto по intent.

**Критерий:** "Напиши функцию факториала" → workflow выполняется.

---

### Этап 8: Frontend — Workflow UI

**Файлы:**
- `frontend/src/features/workflow/WorkflowPanel.tsx`
- `frontend/src/features/workflow/useWorkflowStream.ts`
- `frontend/src/api/client.ts` — postWorkflow, getWorkflowStream

**UI:**
- Этапы: plan → tests → code → validation
- Код стримится в IDE-панель (уже есть layout split)
- Индикатор текущего шага

**Критерий:** В UI видны этапы, код появляется по мере генерации.

---

### Этап 9: Retry, Validator, polish

- Retry для LLM (tenacity или custom)
- Validator: subprocess для запуска тестов (или mock для MVP)
- Обработка ошибок, логирование

---

## Упрощения для MVP (Phase 3)

| Компонент | MVP | Полная версия |
|-----------|-----|---------------|
| Researcher | Stub (пустой контекст) | RAG (Phase 4) |
| Debugger | Пропуск или 1 retry в coder | Отдельный узел |
| Reflection/Critic | Пропуск | Отдельные узлы |
| Checkpointing resume | Опционально | Полная поддержка |
| Validator | Mock (всегда OK) или subprocess | Реальный pytest |

---

## Порядок выполнения (чеклист)

- [ ] 1. Domain: WorkflowState, EventType
- [ ] 2. Agents: planner, tests_writer, coder, validator (один стиль, callback)
- [ ] 3. Retry wrapper для LLM
- [ ] 4. LangGraph: граф, intent_node, conditional
- [ ] 5. WorkflowUseCase
- [ ] 6. API: POST /workflow, SSE stream
- [ ] 7. Роутинг: code intent → workflow
- [ ] 8. Frontend: WorkflowPanel, useWorkflowStream
- [ ] 9. Validator (subprocess или mock)
- [ ] 10. Тесты, ruff, проверка по check.md

---

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| Граф слишком сложный | Начать с intent → planner → coder → END |
| Стриминг ломает checkpointing | События вне state, state минимальный |
| Validator блокирует | Mock для MVP, subprocess позже |
| Дублирование с Chat | Чёткий роутинг: intent → chat | workflow |
