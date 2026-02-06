# Полировка бэкенда — чеклист

Фокус: вылизать бэкенд к моменту появления сильных локальных LLM. Порядок — по приоритету и зависимостям.

---

## 1. Качество кода (Часть 5)

### 1.1 DI — завершить проверку

- [x] Глобальные переменные → Container (store, improvement, file_writer, project_analyzer, code_security, metrics, command_registry, prompt_library).
- [x] Фаза 1 — итоговая проверка: старых синглтонов не осталось; get_* в dependencies → container; get_default_registry делегирует в container.

### 1.2 project_analyzer — разбить на модули

Детали: [PART5_PLAN.md](PART5_PLAN.md) — Фаза 2.

| Шаг | Описание | Статус |
|-----|----------|--------|
| 2.1 | Вынести dataclasses в `analyzer/models.py` (FileMetrics, SecurityIssue, ArchitectureInfo, ProjectAnalysis) | ✅ |
| 2.2 | Вынести сканирование безопасности в `security_scanner.py` | ✅ |
| 2.3 | Вынести расчёт метрик/сложности в `file_metrics.py` | ✅ |
| 2.4 | По желанию: architecture, code_smells в отдельные модули | ✅ |

**Критерий:** project_analyzer.py — оркестрация < ~350 строк; логика в отдельных модулях. **Фаза 2 завершена.**

### 1.3 Большие файлы — вынести логику

Детали: [PART5_PLAN.md](PART5_PLAN.md) — Фаза 3.

| Файл | Действие | Статус |
|------|----------|--------|
| `improvement_graph.py` | Промпты и хелперы (build_plan_prompt, build_code_prompt) в improvement_prompts.py | ✅ |
| `deep_analyzer.py` | Промпты в deep_analysis_prompts.py; RAG в deep_analysis_rag.py (gather_initial_rag, targeted_rag) | ✅ |
| `web_search.py` | Форматирование и провайдеры (URL/заголовки) в функции/стратегии | ✅ |

---

## 2. Надёжность и безопасность

| Пункт | Где | Статус |
|-------|-----|--------|
| **FileService._is_safe_path** | Проверка через `relative_to(root)` вместо `startswith` (path traversal) | ✅ |
| **Тесты без Ollama** | test_chat_code_returns_response: skip при недоступности LLM (fixture llm_available в conftest) | ✅ |
| **Логи в файл** | Уже есть: config `log_file`, ротация, вывод в output/tai.log | ✅ |
| **Pydantic-валидация** | Field constraints (min_length, max_length, ge, le) на всех request-моделях API | ✅ |
| **HTTPException стандартизация** | Все роутеры: `try/except → logger.exception → HTTPException(500/400/404)` | ✅ |
| **Path validation** | `_resolve_path_allowed` и `_ensure_path_allowed` в роутерах | ✅ |

---

## 3. Логирование и наблюдаемость

| Пункт | Описание | Статус |
|-------|----------|--------|
| **logger во всех модулях** | `logging.getLogger(__name__)` в каждом файле src/ | ✅ |
| **Silent exceptions** | Все `except: pass` заменены на `logger.warning/debug(exc_info=True)` | ✅ |
| **Lazy %s форматирование** | Все f-string в вызовах логгера → `%s` (performance) | ✅ |
| **Retry logging** | `tenacity.before_sleep` callback в LLM helpers | ✅ |
| **Startup/shutdown** | `log.info("startup_begin/complete")`, shutdown cleanup (HTTP pool, LLM client) | ✅ |

---

## 4. Производительность и старт

| Пункт | Описание | Статус |
|-------|----------|--------|
| **Прогрев кэша моделей** | В lifespan после validate_models_config один раз прогреть кэш селектора моделей (list_models), чтобы первый запрос не ждал | ✅ |
| **Graceful shutdown** | `HTTPPool.reset()` + `container.llm.close()` в lifespan | ✅ |
| **CACHE_TTL моделей** | Опционально: для single-user поднять до 2–5 мин | ⬜ |

---

## 5. Тесты и CI

| Пункт | Описание | Статус |
|-------|----------|--------|
| **Быстрый CI** | Зафиксировать маркер `pytest -m "not slow"` в CONTRIBUTING или CI | ✅ |
| **Unit-тесты** | 181 тест проходит, 0 ошибок | ✅ |
| **Ruff lint** | `ruff check src/` — 0 ошибок | ✅ |
| **Покрытие критичных путей** | Чат, агент, improve, analyze, RAG — по желанию замер покрытия и доп. тесты | ⬜ |

---

## 6. Типизация и API

| Пункт | Описание | Статус |
|-------|----------|--------|
| **Return type hints** | Все route handlers имеют явные `-> dict`, `-> EventSourceResponse` и т.д. | ✅ |
| **Any → конкретные типы** | RAGPort вместо Any, LLMMessage и др. | ✅ |
| **Naming conflicts** | SearchRequest → WebSearchRequest в assistant.py | ✅ |
| **Unused imports** | Убраны (WorkflowResponse и др.) | ✅ |
| **OpenAPI/документация** | /docs актуален; при добавлении эндпоинтов — описание и примеры | по мере изменений |

---

## 7. Общие утилиты

| Пункт | Описание | Статус |
|-------|----------|--------|
| **LLM Fallback** | `generate_with_fallback()` / `stream_with_fallback()` в `shared/llm_fallback.py` | ✅ |
| **ToolExecutor dispatch** | Словарь вместо if-elif цепочки | ✅ |

---

## Итог

**Основная полировка бэкенда завершена.** Проект проверен на работоспособность:

- ✅ Приложение импортируется и компилируется без ошибок
- ✅ Ruff lint: 0 ошибок
- ✅ 181 unit-тест проходит
- ✅ Сервер запускается, все эндпоинты отвечают
- ✅ Pydantic-валидация работает на всех входных моделях

**Остаётся (низкий приоритет):**
- Увеличить CACHE_TTL для моделей (2–5 мин)
- Расширить покрытие unit-тестами

---

## Связанные документы

- [PART5_PLAN.md](PART5_PLAN.md) — пошаговый план Части 5 (DI, project_analyzer, большие файлы).
- [ROADMAP.md](ROADMAP.md) — стратегия, текущее состояние, полировка UX.
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — слои, потоки данных, инженерные решения.
