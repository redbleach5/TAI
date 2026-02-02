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

**Критерий:** project_analyzer.py — оркестрация < ~350 строк; логика в отдельных модулях. **Фаза 2 завершена:** models, security_scanner, file_metrics, architecture, code_smells вынесены.

### 1.3 Большие файлы — вынести логику

Детали: [PART5_PLAN.md](PART5_PLAN.md) — Фаза 3.

| Файл | Действие | Статус |
|------|----------|--------|
| `improvement_graph.py` | Промпты и хелперы (build_plan_prompt, build_code_prompt) в improvement_prompts.py | ✅ |
| `deep_analyzer.py` | Промпты в константы; RAG-логика и шаги analyze() в отдельные методы/модули | ⬜ |
| `web_search.py` | Форматирование и провайдеры (URL/заголовки) в функции/стратегии | ⬜ |

---

## 2. Надёжность и безопасность

| Пункт | Где | Статус |
|-------|-----|--------|
| **FileService._is_safe_path** | Проверка через `relative_to(root)` вместо `startswith` (path traversal) | ✅ |
| **Тесты без Ollama** | test_chat_code_returns_response: skip при недоступности LLM (fixture llm_available в conftest) | ✅ |
| **Логи в файл** | Уже есть: config `log_file`, ротация, вывод в output/tai.log | ✅ |

---

## 3. Производительность и старт

| Пункт | Описание | Статус |
|-------|----------|--------|
| **Прогрев кэша моделей** | В lifespan после validate_models_config один раз прогреть кэш селектора моделей (list_models), чтобы первый запрос не ждал | ⬜ |
| **CACHE_TTL моделей** | Опционально: для single-user поднять до 2–5 мин | ⬜ |

---

## 4. Тесты и CI

| Пункт | Описание | Статус |
|-------|----------|--------|
| **Быстрый CI** | Зафиксировать маркер `pytest -m "not slow"` в CONTRIBUTING или CI | ⬜ |
| **Покрытие критичных путей** | Чат, агент, improve, analyze, RAG — по желанию замер покрытия и доп. тесты | ⬜ |

---

## 5. API и конфиг

| Пункт | Описание | Статус |
|-------|----------|--------|
| **Логирование** | Уровень, файл, ротация — в конфиге и UI | ✅ |
| **OpenAPI/документация** | /docs актуален; при добавлении эндпоинтов — описание и примеры | по мере изменений |

---

## Порядок работ (рекомендуемый)

1. **Сначала:** 1.1 (итоговая проверка DI), 2 (FileService._is_safe_path, тесты без Ollama).
2. **Затем:** 1.2 project_analyzer (2.1 → 2.2 → 2.3).
3. **Потом:** 1.3 большие файлы (improvement_graph, deep_analyzer, web_search — по одному).
4. **По желанию:** 3 (прогрев кэша, CACHE_TTL), 4 (CI, покрытие).

---

## Связанные документы

- [PART5_PLAN.md](PART5_PLAN.md) — пошаговый план Части 5 (DI, project_analyzer, большие файлы).
- [ROADMAP.md](ROADMAP.md) — стратегия, текущее состояние, полировка UX.
- [ARCHITECTURE.md](ARCHITECTURE.md) — слои и потоки данных.
