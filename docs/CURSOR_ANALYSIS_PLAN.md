# План достижения уровня Cursor AI в анализе

## Текущее состояние
- DeepAnalyzer: статика + RAG (4 запроса, ~10 чанков) + LLM
- Один проход, общий промпт

## Пошаговый план

### Phase 1: Ключевые файлы (быстрый выигрыш) ✓
- [x] Автоматически включать: README.md, pyproject.toml, package.json, main.py, app.py, src/main.py
- [x] Читать первые 80 строк каждого (до 4K символов)
- [x] Добавить в промпт перед статикой

### Phase 2: Расширенный RAG ✓
- [x] 8 запросов вместо 4
- [x] Запросы: архитектура, конфиг, API, сложность, ошибки, зависимости, тесты, модели
- [x] Лимит 25 чанков, 3 на запрос
- [x] Дедупликация по source

### Phase 3: Определение фреймворка ✓
- [x] По pyproject.toml: FastAPI, Django, Flask
- [x] По package.json: React, Next.js
- [x] По структуре: src/api, frontend/
- [x] framework_id: "fastapi" | "react" | "django" | "generic"

### Phase 4: Промпты под фреймворк ✓
- [x] FastAPI: routes, dependencies, Pydantic, async
- [x] React: components, hooks, state, TypeScript
- [x] Django: models, views, migrations
- [x] Generic: общий промпт

### Phase 5: Многошаговый анализ (отложено)
- [ ] Шаг 1: LLM выделяет 3–5 проблемных модулей
- [ ] Шаг 2: RAG по каждому → углублённый анализ
- [ ] Шаг 3: Финальный синтез
- Сложность vs выигрыш — отложено

## Реализация

- Phase 1–4 реализованы в `src/application/analysis/deep_analyzer.py`

## Дальнейшие шаги

Полный план выхода на уровень Cursor AI (анализ + написание кода): **`CURSOR_LEVEL_ROADMAP.md`**
