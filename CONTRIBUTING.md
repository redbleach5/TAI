# Руководство по внесению вклада

Спасибо за интерес к проекту TAI. Ниже — как внести вклад.

## Требования

- Python 3.11+
- Node.js 20+
- Ollama или LM Studio (для локального LLM)

## Разработка

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# Опционально: cp .env.example .env и настройте переменные
uvicorn src.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Тесты

```bash
pytest                        # полный набор
pytest tests/unit/            # только unit-тесты
pytest -m "not slow"          # без тестов с реальным LLM (для CI)
ruff check src/               # линтер
```

Долгие тесты помечены `@pytest.mark.slow`; полный набор — `pytest` (см. [pyproject.toml](pyproject.toml) — `tool.pytest.ini_options.markers`).

## Архитектура

Проект следует слоистой архитектуре:

- **API** — FastAPI routes, валидация запросов (Pydantic), DI через `Depends()`
- **Application** — Use Cases (ChatUseCase, AgentUseCase, WorkflowUseCase, ImprovementUseCase)
- **Domain** — Entities, Ports (Protocol), Services
- **Infrastructure** — Adapters (Ollama, LM Studio, ChromaDB, agents)
- **Shared** — Кросс-слойные утилиты (structlog, логирование)

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

План развития и приоритеты: [docs/dev/ROADMAP.md](docs/dev/ROADMAP.md).

## Стиль кода

- **Python:** ruff для линтинга, black-совместимый формат
- **TypeScript:** ESLint из шаблона Vite
- **Промпты и structured output:** английский язык
- **UI-тексты:** русский язык

### Стандарты кода (backend)

При внесении изменений в бэкенд придерживайтесь следующих правил:

**Логирование:**
- Каждый модуль: `import logging; logger = logging.getLogger(__name__)`
- Lazy-форматирование: `logger.debug("Processing %s", path)` (НЕ f-string)
- Все `except` блоки должны логировать ошибку (не `pass` молча)
- API-роутеры: `logger.exception(...)` перед `HTTPException`

**Обработка ошибок:**
- API: `try/except → logger.exception → HTTPException(400/404/500)`
- Application: `logger.warning/error` с `exc_info=True`
- Infrastructure: `logger.warning/debug` с `exc_info=True`

**Валидация:**
- Все Pydantic request-модели используют `Field(min_length=..., max_length=..., ge=..., le=...)`
- Пути: `max_length=1024`
- Текст: `max_length` зависит от назначения поля

**Типизация:**
- Все route handlers имеют явный return type (`-> dict`, `-> EventSourceResponse` и т.д.)
- Избегать `Any` — использовать конкретные типы или протоколы

## Pull Request

1. Создайте ветку от `main`
2. Внесите изменения, добавьте тесты при необходимости
3. Убедитесь, что `pytest tests/unit/` и `ruff check src/` проходят
4. Опишите изменения в PR

## Вопросы

Откройте [issue](https://github.com/redbleach5/TAI/issues) в репозитории.
