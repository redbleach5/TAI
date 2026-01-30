# Следующие шаги

**Обновлено:** 2026-01-30

## Выполнено (Phase 0–4)

- [x] Phase 0: Фундамент — Ollama + LM Studio, config, CORS, rate limit, health
- [x] Phase 1: Chat — SSE, ConversationMemory, intent, layout
- [x] Phase 2: Model Router — per-provider overrides, fallback
- [x] Phase 3: Workflow — LangGraph, planner → researcher → tests → coder → validator
- [x] Phase 4: RAG — ChromaDB, embeddings, researcher node
- [x] Phase 5: IDE — IDEPanel, Copy, Download, layout split

## Приоритет: Phase 6 — Reasoning, полировка

1. ~~Reasoning-модели — парсинг `<think>`, стриминг thinking~~ ✓
2. Settings UI — редактор config через API
3. Run (опционально) — subprocess с таймаутом или «Copy to run locally»

## Phase 6 — Reasoning, полировка

1. Reasoning-модели — парсинг `<think>`, стриминг thinking
2. Settings UI — редактор config через API
3. Run (опционально) — subprocess для выполнения кода

## Связанные документы

- [plan.md](../plan.md) — полный план
- [check.md](../check.md) — чеклист проверки
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура
