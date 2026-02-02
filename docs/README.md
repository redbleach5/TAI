# Документация TAI

Краткий индекс документации проекта.

---

## Документы

| Документ | Назначение |
|----------|------------|
| **[ROADMAP.md](ROADMAP.md)** | План развития: стратегия (фокус на полировке бэкенда), текущее состояние, дорожная карта, порядок работ, известные проблемы |
| **[BACKEND_POLISH.md](BACKEND_POLISH.md)** | Чеклист полировки бэкенда: качество кода (DI, project_analyzer, большие файлы), надёжность, производительность, тесты |
| [PART5_PLAN.md](PART5_PLAN.md) | Пошаговый план Части 5: DI, разбиение project_analyzer, вынос логики из больших файлов |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектура: слои, потоки данных (чат, RAG, workflow) |
| [CHECKLIST.md](CHECKLIST.md) | Руководство по ручной проверке по фазам (запуск, чат, workflow, RAG, IDE и т.д.) |
| [WEB_SEARCH.md](WEB_SEARCH.md) | Веб-поиск (@web): SearXNG (свой URL), Brave, Tavily — настройка по образцу Cherry Studio |
| [ANALYSIS_QUALITY_ASSESSMENT.md](ANALYSIS_QUALITY_ASSESSMENT.md) | Оценка качества анализа по запросу в чате (vs Cursor), что улучшить |
| [OPEN_SOURCE_ALTERNATIVES.md](OPEN_SOURCE_ALTERNATIVES.md) | Анализ: где уже есть open-source решения (чанкинг, .gitignore, граф зависимостей, веб-поиск и др.), рекомендации по внедрению |
| [TASK_DISPATCHER_ROUTER.md](TASK_DISPATCHER_ROUTER.md) | Нужен ли диспетчер/роутер задач: текущий роутинг, когда вводить, варианты (Task Router, очередь для тяжёлых задач, Celery/ARQ) |

---

## Где что искать

- **«Что сделано и что делать дальше?»** → [ROADMAP.md](ROADMAP.md)
- **«Чем заняться по бэкенду?»** → [BACKEND_POLISH.md](BACKEND_POLISH.md)
- **«Как устроен проект?»** → [ARCHITECTURE.md](ARCHITECTURE.md)
- **«Как проверить после изменений?»** → [CHECKLIST.md](CHECKLIST.md)
