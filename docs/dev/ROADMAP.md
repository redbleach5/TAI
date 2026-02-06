# План развития TAI

Единый документ по развитию проекта: текущее состояние, приоритеты и дорожная карта до уровня Cursor AI.

---

## Стратегия (фокус)

**Возможности проекта уже превосходят то, что текущие локальные модели стабильно раскрывают.** Приоритет — **полировка бэкенда** — **завершена**: архитектура, качество кода, тесты, стабильность, производительность, логирование, валидация, типизация.

- **Сделано:** бэкенд вылизан — API стандартизирован (HTTPException, Pydantic Field validation), логирование во всех слоях (lazy %s), silent exceptions устранены, return types, LLM fallback, graceful shutdown, 181 unit-тест, ruff 0 ошибок. Фронт — UX полировка (Escape, подсказки, ресайз).
- **Отложено до появления сильных локальных моделей:** фичи, сильно зависящие от качества модели (правила проекта в контексте, инлайн tab-completion в редакторе и т.п.). Инфраструктура под них уже есть (агент, tools, RAG, improvement).

Чеклист по полировке бэкенда: [BACKEND_POLISH.md](BACKEND_POLISH.md) — **основная работа завершена**.

---

## Текущее состояние

| Область | Реализовано | Осталось |
|---------|-------------|----------|
| **Чат** | context_files, @rag, @web, @code, auto-RAG, active_file_path, project map, **выбор модели в UI** (request.model) | — |
| **Agent** | read_file, write_file (multi-file), search_rag, run_terminal (cwd, timeout), list_files, get_index_status, index_workspace; **применить/отклонить** правки; **max_iterations в конфиге** (default.toml, [agent]) | — |
| **Workspace** | Открыть папку, индексация, **создать проект с нуля** (POST /workspace/create, UI «Создать проект») | — |
| **Анализ** | DeepAnalyzer: многошаговость (A1), RAG 8 запросов, targeted RAG, отчёт в docs/ANALYSIS_REPORT.md, граф зависимостей (A2), Git-контекст (A3), **покрытие тестами (A4)** — pytest-cov/coverage в промпт | — |
| **Improvement** | plan → code → validate → retry, RAG, related_files, project_map, контекст ошибок (B5), **inline (B6)** — выделенное + diff preview, **стриминг plan→code (C3)** | — |
| **Workflow** | planner → researcher → tests → coder, RAG, project_map | — |

---

## Недавно сделано (Cursor-like)

- **Создание проекта с нуля:** `POST /workspace/create` (создаёт папку при необходимости), UI «Создать проект» в шапке.
- **Терминал агента:** `run_terminal` с опциональными `cwd` (подпапка workspace) и `timeout_seconds` (до 300) — для `npm install`, `pip install` в подпапках.
- **Контекст чата:** workspace в @code/@file, active_file_path, project map и auto-RAG в обычном чате, подсказка про индексацию.
- **Агент:** get_index_status, index_workspace — модель может сама предложить/запустить индексацию.
- **Анализ:** полный отчёт сохраняется в `docs/ANALYSIS_REPORT.md`, в чате — краткое резюме и кнопка «Открыть отчёт».
- **Применить/отклонить правки (Cursor-like):** в режиме агента вызовы `write_file` не пишут на диск сразу; в чате показываются «Предложенные изменения» с diff и кнопками «Применить» и «Отклонить». Параметр запроса `apply_edits_required` (по умолчанию true в режиме agent).
- **Выбор модели в чате:** выбранная в UI модель передаётся в `request.model` и используется бэкендом (обычный чат и стрим).
- **Настройки (расширение):** в разделе «Настройки» — Ollama (host, timeout, num_ctx, num_predict), LM Studio (base_url, timeout, max_tokens), контекст чата (max_context_messages). Сохранение в `development.toml`.
- **Производительность моделей:** опциональные num_ctx/num_predict (Ollama) и max_tokens (OpenAI-совместимый) в конфиге и в UI для максимума контекста и длины ответа.
- **C3 Стриминг улучшений:** при включённом «Стрим» в чате улучшение файла идёт через POST /improve/run/stream; в сообщении ассистента в реальном времени показываются «План» и «Код», затем результат (diff/применить).

---

## Дорожная карта

### Часть 1: Анализ

| Фаза | Описание | Статус |
|------|----------|--------|
| **A1** Многошаговый анализ | Статика + ключевые файлы → RAG по модулям → финальный синтез | ✅ |
| **A2** Граф зависимостей | Парсер импортов (Python/TS), граф, циклы, неиспользуемые импорты | ✅ |
| **A3** Git-контекст | git log (недавние/часто меняющиеся файлы) в промпт анализа | ✅ |
| **A4** Покрытие тестами | pytest-cov/coverage в промпт | ✅ |

### Часть 2: Написание кода

| Фаза | Описание | Статус |
|------|----------|--------|
| **B1** RAG в Improvement | RAG по file_path + issue, релевантные чанки в plan/code | ✅ |
| **B2** Project map в генерацию | Coder и Improvement получают project_map | ✅ |
| **B3** Multi-file edits | Agent: несколько write_file за ответ; Improvement: related_files | ✅ |
| **B4** Авто-RAG в чат | RAG по запросу при отправке, топ-5 чанков в контекст | ✅ |
| **B5** Контекст ошибок | Retry с полным stack trace, RAG по ошибке, промпт «похожий код» | ✅ |
| **B6** Inline-редактирование | «Улучшить выделенное», diff preview, partial edits | ✅ |

### Часть 3: Agent и UX

| Фаза | Описание | Статус |
|------|----------|--------|
| **C1** Agent — контекст | search_rag по запросу, project_map в system, подсказки по read_file | ✅ |
| **C2** Multi-file write | Парсинг нескольких write_file за ответ | ✅ |
| **C2.1** Применить/отклонить правки | Предложенные изменения по файлам, кнопки «Применить» и «Отклонить» в чате (Cursor-like) | ✅ |
| **C3** Streaming улучшений | Improvement: стриминг plan → code в реальном времени | ✅ |
| **C3.1** Без хардкода намерений | Не ветвить по ключевым словам (isAnalyzeIntent); все сообщения в чат; «анализ проекта» как tool агента (run_project_analysis), как у Cursor | ✅ |

#### План реализации C3.1: свобода действий модели

Цель: убрать хардкод намерений во фронте; все сообщения отправлять в чат; модель сама решает, когда запускать анализ, поиск в интернете и т.д. — через инструменты (как у Cursor).

| Шаг | Описание | Файлы |
|-----|----------|--------|
| 1 | **Backend: tool `run_project_analysis`** — добавить инструмент агента с опциональным аргументом `question?: string`. Внутри вызвать DeepAnalyzer (текущий `/api/analyze/project/deep`), вернуть краткое резюме + путь к отчёту (или вставить резюме в Observation). При `question` — передать в анализатор, чтобы в отчёт попал блок «Ответ на вопрос» (если бэкенд анализа это поддержит). | `agent/tools.py`, `agent/ollama_tools.py`, вызов DeepAnalyzer или API analyze |
| 2 | **Backend: опционально `web_search` как tool** — если нужен веб-поиск по решению модели (не только по @web в тексте), добавить tool `web_search(query)` и вызывать существующий `multi_search`. Модель сама решит, когда искать в интернете. | `agent/tools.py`, `agent/ollama_tools.py`, `infrastructure/services/web_search.py` |
| 3 | **Frontend: убрать ветвление по намерению** — удалить вызов `isAnalyzeIntent(text)` и `onAnalyzeRequest()` в `send()`. Все сообщения отправлять в чат (POST /chat/stream). Кнопку «Анализ» в UI оставить: по клику отправлять в чат сообщение вида «Проанализируй этот проект» (модель вызовет tool). | `useChat.ts` (удалить ветку с onAnalyzeRequest), `ChatPanel.tsx` (кнопка «Анализ» → send("Проанализируй этот проект") или аналог) |
| 4 | **Frontend: отображение результата анализа из чата** — если модель вызвала `run_project_analysis` и вернула в Observation путь к отчёту (report_path), показывать в сообщении кнопку «Открыть отчёт» (как сейчас для ответа /analyze/project/deep). Для этого либо передавать report_path в стриме (новый тип события), либо модель вставляет ссылку в текст — тогда парсить или договориться о формате. | `useChat.ts`, `ChatMessage.tsx`, бэкенд стрим (опционально событие `report_path`) |
| 5 | **Очистка** — удалить `ANALYZE_PATTERNS`, `QUESTION_LIKE`, `isAnalyzeIntent` из фронта (или оставить только для кнопки «Анализ» как подсказку, без ветвления). Убрать прямой вызов `POST /api/analyze/project/deep` из ChatPanel; анализ только через агента. | `useChat.ts`, `ChatPanel.tsx` |

**Порядок:** 1 → 3 → 4 (минимум: анализ как tool, всё в чат). Шаги 2 и 5 — по желанию.

**Критерий готовности:** Пользователь пишет «проанализируй проект» или «может ли этот проект искать в интернете?» → сообщение уходит в чат → модель (в режиме агента) при необходимости вызывает `run_project_analysis` или отвечает из контекста/tools. Нет ветвления по ключевым словам во фронте.

---

### Часть 4: Cursor-like (проект с нуля)

| Пункт | Описание | Статус |
|-------|----------|--------|
| Создать проект | API create workspace + UI «Создать проект» | ✅ |
| Терминал: cwd + timeout | run_terminal(cwd, timeout_seconds) для подпапок и долгих команд | ✅ |
| max_iterations в конфиг | Настраиваемый лимит итераций агента (по умолчанию 15–20) | ✅ |

### Часть 5: Качество кода

| Пункт | Статус |
|-------|--------|
| tool_parser: статический import json | ✅ |
| Глобальные переменные → DI | ✅ (store, improvement, file_writer, project_analyzer в Container) |
| project_analyzer: разбить на модули | ✅ |
| Большие файлы: вынести логику | ✅ |

**Пошаговый план:** [PART5_PLAN.md](PART5_PLAN.md) — чеклист по фазам 1 (DI), 2 (project_analyzer), 3 (большие файлы).

---

## Критерии «уровня Cursor»

- [x] **Чат:** авто-RAG, открытые файлы, active_file_path, project map.
- [x] **Генерация:** RAG + project_map в контексте, multi-file (agent + improvement).
- [x] **Agent:** богатый контекст, multi-file write, применить/отклонить предложенные правки, run_terminal в подпапках с таймаутом, индексация по запросу.
- [x] **Проект с нуля:** создать папку из UI → агент пишет файлы и запускает команды.
- [x] **Анализ:** многошаговый + граф зависимостей ✅ + Git ✅ + покрытие тестами (A4) ✅.
- [x] **Improvement:** полный stack trace при retry, контекст ошибок (B5).

---

## Критически не хватает для уровня Cursor

| Пункт | Описание | Приоритет |
|-------|----------|-----------|
| **Правила проекта (.cursorrules)** | В Cursor в контекст подмешиваются правила из `.cursorrules` (и пользовательские). Сейчас в TAI только глобальные промпты режимов; нет чтения файла правил из корня workspace и добавления в system/контекст чата и агента. | **Отложено** — до появления сильных локальных моделей (см. «Стратегия»). |
| **Инлайн-подсказки (tab completion)** | Cursor даёт подсказки «по мере набора» в редакторе (ghost text, Tab принять). В TAI есть только чат, Improve и Workflow — нет автодополнения кода в редакторе. | **Отложено** — сильно зависит от качества модели. |
| **Полировка UX** | Завершена. Escape для Настроек и Git diff, тултипы, тосты, ресайз — всё реализовано. | ✅ |
| **Единый контекст правил** | Читать из workspace файл правил (`.cursor/rules/*.mdc` или `.cursorrules`), подмешивать в system prompt чата и агента. | **Отложено** — вместе с правилами проекта. |

**Итог:** По возможностям (чат, агент, multi-file, apply/reject, RAG, анализ) TAI уже близок к Cursor. Полировка бэкенда завершена ([BACKEND_POLISH.md](BACKEND_POLISH.md)); правила проекта и инлайн-подсказки — когда появятся топовые локальные LLM.

---

## Полировка и оптимизация: выжать максимум из того, что есть

**Идея:** Критический рывок — не только новые фичи, а **оптимизация и полировка** уже существующего. Ниже — только то, что **ещё не реализовано** (по результатам проверки кода).

### Уже реализовано (убрано из планов)

- **Пустое состояние чата:** подсказки, @web/@code/@rag, кликабельные предложения (`ChatPanel.tsx`, `chat-panel__empty`).
- **Copy на блоках кода:** `CodeBlockWithCopy` в `ChatMessage.tsx`, кнопка «Копировать»/«Скопировано».
- **Фокус после отправки:** `ChatInput.tsx` — `setTimeout(() => inputRef.current?.focus(), 0)` в `handleSubmit`.
- **Ресайз панели чата:** `Layout.tsx` — `handleResizeStart`, `layout__chat-resizer`, тултип «Тянуть для изменения ширины чата»; ширина персистится.
- **Тосты:** `ToastContext.tsx`, позиция `bottom/right` (не перекрывают ввод), анимация `toastSlideIn` в `App.css`.
- **Тултипы:** `Tooltip` на чаты, новый чат, контекст («AI видит открытые файлы»), свернуть чат, **Анализ проекта**, **Улучшить файл**, **Весь файл или выделенный фрагмент (с diff)**, **Сгенерировать код**, настройки, сайдбар (Файлы, Git, RAG), ресайзер, модель; в `ChatInput` — **Enter — отправить, Shift+Enter — новая строка**, Отправить (Enter).
- **Escape закрывает:** improve diff modal, панели (conversations, templates), `CreateProjectDialog`, `FolderPicker`, создание/переименование в `FileBrowser`.
- **Индикация «печатает»:** `busy = loading || generating || improving`, `Loader2` на кнопках (Анализ, Improve, Generate), блок с `chat-message__content--loading` и точками в чате.
- **Discoverability:** подсказка в пустом состоянии есть; кнопка «Анализ» с тултипом «Анализ проекта»; Improve — тултип «Весь файл или выделенный фрагмент (с diff)».

### 1. UX-полировка — осталось

| Что | Где проверить | Зачем | Статус |
|-----|----------------|--------|--------|
| **Escape для панели «Настройки»** | `Layout.tsx` | keydown Escape → setShowSettings(false) | ✅ |
| **Escape для модалки Git diff** | `GitPanel.tsx` — selectedDiff | keydown Escape → setSelectedDiff(null) | ✅ |

### 2. Производительность — осталось

| Что | Где | Зачем | Статус |
|-----|-----|--------|--------|
| **Прогрев кэша моделей при старте** | `main.py` lifespan, `ModelSelector` | Первый запрос не ждёт `list_models` | ✅ |
| **Graceful shutdown** | `main.py` lifespan | HTTP pool + LLM client cleanup | ✅ |
| **CACHE_TTL для списка моделей** | `model_selector.py` — `CACHE_TTL = 60` | Опционально: для single-user поднять до 2–5 мин | ⬜ |
| **Стриминг** | — | Уже есть для чата, improve, workflow | ✅ |

### 3. Discoverability — осталось (опционально)

| Что | Зачем |
|-----|--------|
| **Режим Агент: подсказка при первом использовании** | Одноразовая подсказка или расширенный тултип: «Модель может читать/писать файлы, искать в коде, запускать команды. Предложенные правки — применить или отклонить.» Сейчас у режима есть описание в `ModeSelector`; можно усилить для Агента. |

### 4. Качество кода и поддержка

| Что | Зачем | Статус |
|-----|--------|--------|
| **Разбить project_analyzer на модули** | Часть 5 — проще тестировать и дорабатывать анализ | ✅ |
| **Вынести логику из больших файлов** | Уменьшить когнитивную нагрузку | ✅ |
| **Быстрый CI: `pytest -m "not slow"`** | Зафиксировать в CONTRIBUTING | ✅ |
| **Логирование во всех модулях** | `logging.getLogger(__name__)` + lazy %s | ✅ |
| **Silent exceptions → logging** | Все `except: pass` заменены | ✅ |
| **Pydantic Field validation** | Ограничения на все request-модели | ✅ |
| **Return type hints** | Явные типы возврата на всех route handlers | ✅ |
| **HTTPException стандартизация** | Единый подход к ошибкам в API | ✅ |
| **LLM Fallback utility** | `shared/llm_fallback.py` | ✅ |
| **ToolExecutor dict dispatch** | Замена if-elif цепочки | ✅ |

### 5. Приоритет внедрения (обновлённый)

1. ~~**Быстро:** Escape для Настроек и Git diff~~ — ✅ сделано.
2. ~~**По желанию:** прогрев кэша моделей в lifespan~~ — ✅ сделано.
3. ~~**Полировка бэкенда**~~ — ✅ завершена (3 волны: стандартизация, логирование, валидация).
4. **По желанию:** увеличение CACHE_TTL (2–5 мин); подсказка для режима Агент при первом использовании.

---

## Рекомендуемый порядок работ

**Уже сделано:** A2 (граф зависимостей), B5 (контекст ошибок), A3 (Git-контекст), A4 (покрытие тестами в анализе), B6 (inline-редактирование: выделенное + diff preview), max_iterations в конфиг, C3.1 (run_project_analysis, сообщения в чат), C3 (стриминг улучшений: plan → code в чате).

**Дальше по приоритету:**

1. ~~**A4** Покрытие тестами в анализе~~ — ✅ сделано.
2. ~~**B6** Inline-редактирование~~ — ✅ сделано.
3. ~~**C3** Стриминг улучшений~~ — ✅ сделано.
4. ~~**Полировка бэкенда**~~ — ✅ завершена. См. [BACKEND_POLISH.md](BACKEND_POLISH.md).

**Низкий приоритет (осталось):**
- Увеличить CACHE_TTL для моделей (2–5 мин)
- Расширить покрытие unit-тестами

---

## Файлы для изменений (по фазам)

| Фаза | Файлы |
|------|-------|
| A1 | `deep_analyzer.py` |
| A2 | Новый `dependency_graph.py`, `deep_analyzer.py` |
| A3 | `deep_analyzer.py`, git commands |
| A4 | `coverage_collector.py`, `deep_analyzer.py` |
| B1 | `improvement_graph.py`, `use_case.py` (improvement) |
| B2 | `workflow/` (coder node), `improvement_graph.py` |
| B3 | `agent/tools.py`, `improvement/use_case.py`, API, UI: Improve форма + related_files |
| B6 | `improvement/dto.py`, `improvement_graph.py`, `improve.py`, `OpenFilesContext`, `MultiFileEditor`, `ChatPanel`, API client |
| B4 | `chat/use_case.py`, `_build_messages` |
| B5 | `improvement_graph.py` |
| C1 | `agent/use_case.py`, `_build_initial_messages` |
| C2 | `agent/tool_parser.py`, `use_case.py` (подтверждение — backend) |
| C3 | `improve.py` (POST /run/stream), `improvement/use_case.py` (improve_file_stream), `api/client.ts` (streamImprove), `ChatPanel.tsx` (handleImprove со стримом) |
| C3.1 | `agent/tools.py`, `agent/ollama_tools.py`, `useChat.ts`, `ChatPanel.tsx`; опционально `web_search` в tools, событие report_path в стриме |

---

## Agent: формат и инструменты

- **ReAct (prompt-based):** ответ LLM содержит `<tool_call>{"tool": "read_file", "path": "..."}</tool_call>`; парсинг в `tool_parser.py`, выполнение в `tools.py` (ToolExecutor). Работает с любыми моделями.
- **Native tools:** при Ollama/LM Studio с tool calling используется `chat_with_tools` / `chat_with_tools_stream`; схема в `ollama_tools.py`.
- **Инструменты:** read_file(path), write_file(path, content), search_rag(query), run_terminal(command, cwd?, timeout_seconds?), list_files(path?), get_index_status(), index_workspace(incremental?). Все пути относительно workspace; run_terminal — whitelist команд.

---

## Контекст чата (поток)

Фронт отправляет: message, history, context_files (открытые в редакторе), active_file_path. Бэкенд: context_files → блок «Open files» в user message; @code/@file разрешаются относительно workspace; auto-RAG подмешивает топ чанков и project map. В агенте — те же открытые файлы + project_map в system, инструменты работают в workspace из projects store.

---

## Анализ: детали фаз (реализовано)

- **Ключевые файлы:** README, pyproject.toml, package.json, main.py, app.py и т.д. — первые 80 строк в промпт.
- **RAG:** 8 запросов (архитектура, конфиг, API, сложность, ошибки, зависимости, тесты, модели), 25 чанков, 3 на запрос, дедупликация по source.
- **Фреймворк:** по pyproject.toml/package.json/структуре определяется FastAPI, React, Django и т.д.; промпты анализа под фреймворк.
- **Многошаговость (A1):** статика + ключевые файлы → RAG по модулям → финальный синтез.

---

## Известные проблемы

- **Path traversal в FileReaderHandler** — исправлено (пути относительно workspace, проверка relative_to).
- **Тест `test_chat_code_returns_response`** — исправлено: skip при недоступности LLM (fixture `llm_available` в conftest).
- **Хост Ollama и LM Studio** — настраиваются в разделе «Настройки» (Ollama host, LM Studio base_url) и в development.toml / .env (OLLAMA_HOST, OPENAI_BASE_URL).
- **FileService._is_safe_path** — исправлено: проверка через `relative_to(root)` вместо `startswith`.
- **Frontend: история в sync-чате** — исправлено (messagesRef для актуальной истории).
- **Container.reset()** — после reset кэш очищается, но `_config_override` остаётся (учитывать в тестах).

---

## Улучшения UI

**Уже реализовано (по проверке кода):** пустое состояние чата с подсказками и @web/@code/@rag; кнопка Copy на блоках кода (`ChatMessage.tsx`); фокус в поле ввода после отправки (`ChatInput.tsx`); ресайз панели чата (`Layout.tsx`, `layout__chat-resizer`); тосты с анимацией, позиция bottom-right (`ToastContext`, `App.css`); тултипы на иконках (чаты, Анализ, Улучшить, контекст, ресайз, Enter/Shift+Enter и др.); индикация «печатает» (busy, Loader2 на кнопках, loading dots в чате); Escape для improve diff, conversations, templates, CreateProject, FolderPicker, FileBrowser create/rename.

**Осталось:** ✅ Все пункты UX-полировки выполнены (Escape для Настроек и Git diff сделаны).

**Низкий приоритет (не в планах):** тёмная/светлая тема; моноширинный шрифт в редакторе; fade-in сообщений; командная палитра Cmd+K; доступность (aria-label, навигация с клавиатуры); мобильная версия.

---

## Связанные документы

- [../ARCHITECTURE.md](../ARCHITECTURE.md) — архитектура: слои, потоки данных.
- [CHECKLIST.md](CHECKLIST.md) — ручная проверка по фазам (запуск, чат, workflow, RAG, IDE и т.д.).

В корне репозитория: [CONTRIBUTING.md](../../CONTRIBUTING.md) — как вносить вклад.
