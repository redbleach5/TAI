# Часть 5: Качество кода — пошаговый план

План рефакторинга: глобальные переменные → DI, разбиение project_analyzer, вынос логики из больших файлов.  
**Большинство пунктов выполнено.** Актуальный чеклист полировки бэкенда: [BACKEND_POLISH.md](BACKEND_POLISH.md).

---

## Обзор текущих глобальных синглтонов

| Файл | Переменная | Кто использует |
|------|------------|----------------|
| `api/routes/improve.py` | `_use_case`, `_file_writer` | Эндпоинты improve (свой get_improvement_use_case) |
| `api/container.py` | `_container` | dependencies.py, main.py — оставляем как единую точку DI |
| `api/routes/projects.py` | `_store` (ProjectsStore) | container (chat), workspace, agent/tools, improve |
| `infrastructure/analyzer/project_analyzer.py` | `_analyzer` | analyze.py, deep_analyzer.py |
| ~~`infrastructure/services/code_security.py`~~ | ~~`_checker`~~ | → Container (code.py через Depends) |
| ~~`infrastructure/services/performance_metrics.py`~~ | ~~`_metrics`~~ | → Container (code.py через Depends) |
| ~~`application/chat/handlers/registry.py`~~ | ~~`_default_registry`~~ | → Container (chat_use_case получает из container) |
| ~~`infrastructure/services/prompt_templates.py`~~ | ~~`_library`~~ | → Container (assistant.py через Depends) |

Опционально (низкий приоритет): `circuit_breaker.py` (_breakers), `http_pool.py` (HTTPPool) — используются LLM и web_search.

---

## Фаза 1: Глобальные переменные → DI через Container

Порядок важен: сначала то, от чего зависят другие (store, затем improvement с file_writer и workspace).

### 1.1 ProjectsStore в Container

- [x] **1.1.1** В `container.py`: добавить `@cached_property def projects_store(self) -> ProjectsStore`. Создавать `ProjectsStore` (логика из `projects.py`: путь к store, загрузка/сохранение). Импорт класса из `src.api.routes.projects` или вынести класс в `src.infrastructure.persistence` / `src.api.store` (по желанию).
- [x] **1.1.2** В `dependencies.py`: добавить `def get_store() -> ProjectsStore: return get_container().projects_store` (если ещё не из dependencies — сейчас get_store в projects.py).
- [x] **1.1.3** В `api/routes/projects.py`: удалить `_store`, заменить использование на `Depends(get_store)` из dependencies; `get_store` оставить в dependencies и импортировать в projects.py из dependencies.
- [x] **1.1.4** В `container.py`: в `chat_use_case` и везде, где вызывается `get_store()`, передавать `self.projects_store` (или getter) в use case / хелперы.
- [x] **1.1.5** Проверить: workspace.py, agent/tools.py, improve.py — все получают store через Depends(get_store); get_store берёт из container.
- [x] **1.1.6** Тесты: запустить `pytest tests/ -v`, проверить проекты и workspace.

**Критерий:** Нет глобального `_store` в projects.py; store создаётся в Container и отдаётся через dependencies.

---

### 1.2 Improvement use case и FileWriter в Container

- [x] **1.2.1** В `container.py`: добавить `@cached_property def file_writer(self) -> FileWriter` (создавать `FileWriter()`).
- [x] **1.2.2** В `container.py`: в `improvement_use_case` передать `file_writer=self.file_writer` и `workspace_path_getter` (лямбда/хелпер, использующий `self.projects_store.get_current()` и путь; при отсутствии current — `Path.cwd()`).
- [x] **1.2.3** В `api/dependencies.py`: добавить `def get_file_writer() -> FileWriter: return get_container().file_writer` (если нужен отдельно для роутов).
- [x] **1.2.4** В `api/routes/improve.py`: удалить `_use_case`, `_file_writer`, локальные `get_file_writer` и `get_improvement_use_case`. Импортировать `get_improvement_use_case` и при необходимости `get_file_writer` из `api.dependencies`. Все эндпоинты оставить с `Depends(get_improvement_use_case)` из dependencies.
- [x] **1.2.5** Убедиться, что `get_improvement_use_case` в dependencies возвращает `get_container().improvement_use_case` и что в container improvement_use_case создаётся с file_writer и workspace_path_getter.
- [x] **1.2.6** Тесты: `pytest tests/`, проверить улучшение (improve) и очередь.

**Критерий:** В improve.py нет глобальных _use_case/_file_writer; improvement и file_writer берутся из Container через dependencies.

---

### 1.3 ProjectAnalyzer в Container

- [x] **1.3.1** В `container.py`: добавить `@cached_property def project_analyzer(self) -> ProjectAnalyzer` (создать `ProjectAnalyzer()` с нужными параметрами, если есть).
- [x] **1.3.2** В `api/dependencies.py`: добавить `def get_analyzer() -> ProjectAnalyzer: return get_container().project_analyzer`.
- [x] **1.3.3** В `api/routes/analyze.py` и везде, где используется get_analyzer: импортировать `get_analyzer` из `api.dependencies` (или оставить импорт из project_analyzer, но сам get_analyzer в dependencies должен вызывать container). Лучше: анализер только через Depends(get_analyzer), а get_analyzer в dependencies возвращает container.project_analyzer.
- [x] **1.3.4** В `infrastructure/analyzer/project_analyzer.py`: удалить глобальный `_analyzer` и функцию `get_analyzer()` (или оставить тонкую обёртку `return get_container().project_analyzer` только если не хотим импортировать container в инфраструктуру; предпочтительно — вызов только из api.dependencies).
- [x] **1.3.5** В `application/analysis/deep_analyzer.py`: анализатор должен получаться извне (через конструктор или вызов get_analyzer из зависимостей). Сейчас deep_analyzer вызывает get_analyzer() напрямую — заменить на зависимость: либо DeepAnalyzer(..., analyzer: ProjectAnalyzer), либо оставить вызов get_analyzer(), но get_analyzer в одном месте (dependencies) и возвращает container.project_analyzer. Проще всего: оставить в deep_analyzer импорт get_analyzer из dependencies (перенести get_analyzer в dependencies, в project_analyzer.py удалить get_analyzer и _analyzer).
- [x] **1.3.6** Обновить `infrastructure/analyzer/__init__.py`: экспортировать класс ProjectAnalyzer, не get_analyzer (или реэкспорт get_analyzer из api.dependencies — нежелательно из-за циклических импортов; лучше анализер получать только в API-слое через Depends).
- [x] **1.3.7** Тесты: проверить analyze и deep_analyzer.

**Критерий:** Нет _analyzer в project_analyzer.py; анализатор создаётся в Container, в API получается через Depends(get_analyzer). deep_analyzer и analyze используют один источник (dependencies → container).

**Примечание по циклам:** Container не должен импортировать api.routes.projects (get_store) до того, как store будет в container. После 1.1 container импортирует только класс ProjectsStore (из одного модуля), создаёт store сам. Тогда deep_analyzer может импортировать get_analyzer из api.dependencies только если у него нет обратной зависимости от application к api. Проверить: deep_analyzer используется в agent и в analyze routes; analyze routes уже импортируют dependencies. Значит, в deep_analyzer лучше принимать analyzer в конструкторе (инжектить из контейнера при создании DeepAnalyzer в agent/analyze), а не вызывать get_analyzer() внутри deep_analyzer — чтобы не тянуть api.dependencies в application/analysis. Итого: в container создаём project_analyzer; при создании DeepAnalyzer (где он создаётся?) — в analyze.py и в agent — передавать analyzer=get_analyzer() из Depends. Тогда deep_analyzer принимает analyzer в __init__ и не вызывает get_analyzer сам. Нужно проверить, где создаётся DeepAnalyzer.

- [x] **1.3.8** Найти все места создания DeepAnalyzer: передать туда `analyzer` из Depends(get_analyzer) или из container. В DeepAnalyzer добавить параметр `analyzer: ProjectAnalyzer` в __init__ и убрать вызов get_analyzer() внутри.

---

### 1.4 CodeSecurityChecker в Container

- [x] **1.4.1** В `container.py`: добавить `@cached_property def code_security_checker(self) -> CodeSecurityChecker` (по умолчанию strict=False). При необходимости второй — `strict_security_checker` (strict=True) или фабрика.
- [x] **1.4.2** В `dependencies.py`: добавить `def get_security_checker(strict: bool = False) -> CodeSecurityChecker` — возвращать container.code_security_checker или container.strict_security_checker в зависимости от strict.
- [x] **1.4.3** В `api/routes/code.py`: оставить Depends(get_security_checker), импорт get_security_checker из dependencies.
- [x] **1.4.4** В `code_security.py`: удалить _checker и логику синглтона из get_security_checker; оставить только фабрику или убрать get_security_checker из модуля (полностью перенести в dependencies).
- [x] **1.4.5** Тесты: test_code_security, test_code.

**Критерий:** Checker создаётся в Container; код получает его через Depends.

---

### 1.5 PerformanceMetrics в Container

- [x] **1.5.1** В `container.py`: добавить `@cached_property def performance_metrics(self) -> PerformanceMetrics`.
- [x] **1.5.2** В `dependencies.py`: добавить `def get_metrics() -> PerformanceMetrics: return get_container().performance_metrics`.
- [x] **1.5.3** В `api/routes/code.py`: использовать Depends(get_metrics), импорт из dependencies.
- [x] **1.5.4** В `performance_metrics.py`: удалить _metrics и синглтон из get_metrics.
- [x] **1.5.5** Тесты: test_performance_metrics, test_code.

**Критерий:** Метрики только из Container через dependencies.

---

### 1.6 CommandRegistry в Container

- [x] **1.6.1** В `container.py`: добавить `@cached_property def command_registry(self) -> CommandRegistry` (создать через get_default_registry() или скопировать логику регистрации команд из registry.py).
- [x] **1.6.2** В `container.py`: в `chat_use_case` передать `command_registry=self.command_registry` вместо вызова get_default_registry().
- [x] **1.6.3** В `dependencies.py`: при необходимости добавить `def get_command_registry() -> CommandRegistry: return get_container().command_registry`.
- [x] **1.6.4** В `application/chat/handlers/registry.py`: убрать _default_registry; get_default_registry() может вызывать get_container().command_registry только если не будет циклического импорта (registry → container → chat_use_case → registry). Безопаснее: в Container создавать CommandRegistry напрямую (скопировать построение из get_default_registry), тогда registry.py только определяет класс и регистрацию, а синглтон убрать; ChatUseCase получает registry из container.
- [x] **1.6.5** В chat/use_case.py: уже принимает command_registry or get_default_registry(); после 1.6.2 всегда передавать из container, убрать fallback на get_default_registry() в use_case или оставить для обратной совместимости тестов.
- [x] **1.6.6** Тесты: test_chat.

**Критерий:** Один CommandRegistry из Container; в chat use case не вызывается глобальный get_default_registry.

---

### 1.7 PromptLibrary в Container

- [x] **1.7.1** В `container.py`: добавить `@cached_property def prompt_library(self) -> PromptLibrary` (создать PromptLibrary — из prompt_templates.py посмотреть, как создаётся библиотека).
- [x] **1.7.2** В `dependencies.py`: добавить `def get_library() -> PromptLibrary: return get_container().prompt_library`.
- [x] **1.7.3** В `api/routes/assistant.py`: заменить вызовы get_library() на Depends(get_library), импорт get_library из dependencies.
- [x] **1.7.4** В `prompt_templates.py`: удалить _library и синглтон из get_library.
- [x] **1.7.5** Тесты: проверить assistant routes.

**Критерий:** Библиотека промптов из Container.

---

### Фаза 1 — итоговая проверка

- [x] Запустить полный набор тестов: `pytest tests/ -v`.
- [x] Убедиться, что в коде не осталось обращений к старым глобальным синглтонам (кроме _container в container.py).
- [x] Обновить ROADMAP.md: в Части 5 отметить «Глобальные переменные → DI» как выполненное.

---

## Фаза 2: project_analyzer — разбить на модули

Текущий размер: ~646 строк. Уже есть отдельно: dependency_graph.py, coverage_collector.py, report_generator.py.

### 2.1 Вынести dataclasses в общий модуль

- [x] **2.1.1** Создать `src/infrastructure/analyzer/models.py`: перенести `FileMetrics`, `SecurityIssue`, `ArchitectureInfo`, `ProjectAnalysis`.
- [x] **2.1.2** В project_analyzer.py: импортировать эти классы из models.py.
- [x] **2.1.3** Обновить импорты в report_generator.py, analyze.py, __init__.py (импорт из analyzer.models).
- [x] **2.1.4** Тесты: test_project_analyzer, test_analyzer.

**Критерий:** Даты анализа живут в analyzer/models.py, project_analyzer только использует их.

---

### 2.2 Вынести сканирование безопасности

- [x] **2.2.1** Создать `src/infrastructure/analyzer/security_scanner.py`: SECURITY_PATTERNS и check_file_security(file_path, base_path) -> list[SecurityIssue].
- [x] **2.2.2** В ProjectAnalyzer: вызывать check_file_security вместо _check_security.
- [x] **2.2.3** Тесты: test_security_scanner.py; test_project_analyzer (security).

**Критерий:** Логика безопасности в отдельном модуле, ProjectAnalyzer её вызывает.

---

### 2.3 Вынести расчёт метрик файла и сложности

- [x] **2.3.1** Создать `src/infrastructure/analyzer/file_metrics.py`: compute_file_metrics, extract_imports, estimate_complexity.
- [x] **2.3.2** В ProjectAnalyzer: заменить _analyze_file на compute_file_metrics; _analyze_architecture использует extract_imports из file_metrics.
- [x] **2.3.3** FileMetrics из models (уже в models.py).
- [x] **2.3.4** Тесты: test_file_metrics.py; test_project_analyzer (метрики, сложность).

**Критерий:** Расчёт метрик и сложности в file_metrics.py; project_analyzer оркестрирует.

---

### 2.4 Архитектура и code smells (по желанию)

- [x] **2.4.1** Вынести _analyze_architecture в `architecture.py` и _find_code_smells в `code_smells.py`.
- [x] **2.4.2** В ProjectAnalyzer остались: _collect_files, _detect_language, вызовы security_scanner, file_metrics, architecture, code_smells, расчёт scores и рекомендаций.

**Критерий:** project_analyzer.py < ~350 строк, читаемая оркестрация. ✅

---

### Фаза 2 — итог

- [x] Запустить тесты анализа и проекта.
- [x] В ROADMAP отметить «project_analyzer: разбить на модули».

---

## Фаза 3: Большие файлы — вынести логику

Приоритет по размеру и связности.

### 3.1 improvement_graph.py (~600 строк)

- [x] **3.1.1** Вынести константы промптов (PLAN_SYSTEM, CODE_SYSTEM) и построение промптов в `improvement_prompts.py` (build_plan_prompt, build_code_prompt).
- [x] **3.1.2** Промпты plan/code строятся в build_plan_prompt(state), build_code_prompt(state); _build_full_content_for_selection остаётся в графе.
- [x] **3.1.3** В файле остались: узлы графа, build_improvement_graph, compile_improvement_graph.

**Критерий:** Промпты и чистая логика текста вынесены; граф остаётся читаемым. ✅

---

### 3.2 deep_analyzer.py (~588 строк)

- [x] **3.2.1** Шаблоны промптов и KEY_FILES в `deep_analysis_prompts.py` (STEP1_MODULES_PROMPT, DEEP_ANALYSIS_PROMPT_*, PROMPTS_BY_FRAMEWORK).
- [x] **3.2.2** RAG: `deep_analysis_rag.py` — RAG_QUERIES, A1_* константы, gather_initial_rag(rag), targeted_rag(rag, modules).
- [x] **3.2.3** analyze() вызывает gather_initial_rag и targeted_rag из модуля; шаги остаются в одном методе с явными комментариями.

**Критерий:** Промпты и RAG-логика выделены в отдельные модули. ✅

---

### 3.3 web_search.py (~619 строк)

- [x] **3.3.1** Вынести форматирование результатов в функцию format_search_results или отдельный модуль formatters.
- [x] **3.3.2** Вынести построение URL/заголовков для каждого провайдера (SearXNG, Brave, Tavily, Google) в маленькие функции или классы-стратегии.
- [x] **3.3.3** Оставить в основном файле оркестрацию: multi_search, выбор провайдера, таймауты.

**Критерий:** Парсинг и форматирование вынесены; основной файл — поток вызовов.

---

### Фаза 3 — итог

- [x] Тесты для затронутых областей (improvement, analysis, web_search при наличии).
- [x] В ROADMAP отметить «Большие файлы: вынести логику».

---

## Порядок выполнения (кратко)

1. **Фаза 1.1** → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7, после каждого шага — тесты.
2. **Фаза 2.1** → 2.2 → 2.3 → (2.4 по необходимости).
3. **Фаза 3.1** → 3.2 → 3.3 (можно параллельно по файлам).

Зависимости: 1.1 до 1.2 (store нужен для improvement); 1.3 можно делать после 1.2; 1.4–1.7 независимы друг от друга после 1.1. Фаза 2 после фазы 1 (get_analyzer уже из container). Фаза 3 в любой момент после стабилизации 1–2.

---

## Связанные документы

- [ROADMAP.md](ROADMAP.md) — Часть 5, таблица «Качество кода».
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — слои и потоки данных.
