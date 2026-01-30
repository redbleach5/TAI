# Руководство по внесению вклада

Спасибо за интерес к проекту CodeGen AI. Ниже — как внести вклад.

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
pytest
ruff check src/
```

## Архитектура

Проект следует слоистой архитектуре:

- **API** — FastAPI routes, только маршрутизация и валидация
- **Application** — Use Cases (ChatUseCase, WorkflowUseCase)
- **Domain** — Entities, Ports (Protocol), Services
- **Infrastructure** — Adapters (Ollama, LM Studio, ChromaDB, agents)

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Стиль кода

- **Python:** ruff для линтинга, black-совместимый формат
- **TypeScript:** ESLint из шаблона Vite
- **Промпты и structured output:** английский язык
- **UI-тексты:** русский язык

## Pull Request

1. Создайте ветку от `main`
2. Внесите изменения, добавьте тесты при необходимости
3. Убедитесь, что `pytest` и `ruff check` проходят
4. Опишите изменения в PR

## Вопросы

Откройте issue в репозитории.
