# План развития TAI

Единый документ по развитию проекта: текущее состояние, приоритеты и дорожная карта до уровня Cursor AI.

---

## Текущее состояние

| Область | Реализовано | Осталось |
|---------|-------------|----------|
| **Чат** | context_files, @rag, @web, @code, auto-RAG, active_file_path, project map в контексте | — |
| **Agent** | read_file, write_file (multi-file), search_rag, run_terminal (cwd, timeout), list_files, get_index_status, index_workspace; **применить/отклонить** предложенные правки (Cursor-like) | max_iterations в конфиг |
| **Workspace** | Открыть папку, индексация, **создать проект с нуля** (POST /workspace/create, UI «Создать проект») | — |
| **Анализ** | DeepAnalyzer: многошаговость (A1), RAG 8 запросов, targeted RAG, отчёт в docs/ANALYSIS_REPORT.md, граф зависимостей (A2), Git-контекст (A3) | Покрытие тестами (A4) |
| **Improvement** | plan → code → validate → retry, RAG, related_files, project_map | Контекст ошибок (B5), стриминг plan→code (C3) |
| **Workflow** | planner → researcher → tests → coder, RAG, project_map | — |

---

## Недавно сделано (Cursor-like)

- **Создание проекта с нуля:** `POST /workspace/create` (создаёт папку при необходимости), UI «Создать проект» в шапке.
- **Терминал агента:** `run_terminal` с опциональными `cwd` (подпапка workspace) и `timeout_seconds` (до 300) — для `npm install`, `pip install` в подпапках.
- **Контекст чата:** workspace в @code/@file, active_file_path, project map и auto-RAG в обычном чате, подсказка про индексацию.
- **Агент:** get_index_status, index_workspace — модель может сама предложить/запустить индексацию.
- **Анализ:** полный отчёт сохраняется в `docs/ANALYSIS_REPORT.md`, в чате — краткое резюме и кнопка «Открыть отчёт».
- **Применить/отклонить правки (Cursor-like):** в режиме агента вызовы `write_file` не пишут на диск сразу; в чате показываются «Предложенные изменения» с diff и кнопками «Применить» и «Отклонить». Применить — запись через API; отклонить — правка снимается. Параметр запроса `apply_edits_required` (по умолчанию true в режиме agent).

---

## Дорожная карта

### Часть 1: Анализ

| Фаза | Описание | Статус |
|------|----------|--------|
| **A1** Многошаговый анализ | Статика + ключевые файлы → RAG по модулям → финальный синтез | ✅ |
| **A2** Граф зависимостей | Парсер импортов (Python/TS), граф, циклы, неиспользуемые импорты | ✅ |
| **A3** Git-контекст | git log (недавние/часто меняющиеся файлы) в промпт анализа | ✅ |
| **A4** Покрытие тестами | pytest-cov/coverage в промпт | ⬜ |

### Часть 2: Написание кода

| Фаза | Описание | Статус |
|------|----------|--------|
| **B1** RAG в Improvement | RAG по file_path + issue, релевантные чанки в plan/code | ✅ |
| **B2** Project map в генерацию | Coder и Improvement получают project_map | ✅ |
| **B3** Multi-file edits | Agent: несколько write_file за ответ; Improvement: related_files | ✅ |
| **B4** Авто-RAG в чат | RAG по запросу при отправке, топ-5 чанков в контекст | ✅ |
| **B5** Контекст ошибок | Retry с полным stack trace, RAG по ошибке, промпт «похожий код» | ✅ |
| **B6** Inline-редактирование | «Улучшить выделенное», diff preview, partial edits | ⬜ |

### Часть 3: Agent и UX

| Фаза | Описание | Статус |
|------|----------|--------|
| **C1** Agent — контекст | search_rag по запросу, project_map в system, подсказки по read_file | ✅ |
| **C2** Multi-file write | Парсинг нескольких write_file за ответ | ✅ |
| **C2.1** Применить/отклонить правки | Предложенные изменения по файлам, кнопки «Применить» и «Отклонить» в чате (Cursor-like) | ✅ |
| **C3** Streaming улучшений | Improvement: стриминг plan → code в реальном времени | ⬜ |
| **C3.1** Без хардкода намерений | Не ветвить по ключевым словам (isAnalyzeIntent); все сообщения в чат; «анализ проекта» как tool агента (run_project_analysis), как у Cursor | ⬜ |

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
| Глобальные переменные → DI | ⬜ |
| project_analyzer: разбить на модули | ⬜ |
| Большие файлы: вынести логику | ⬜ |

---

## Критерии «уровня Cursor»

- [x] **Чат:** авто-RAG, открытые файлы, active_file_path, project map.
- [x] **Генерация:** RAG + project_map в контексте, multi-file (agent + improvement).
- [x] **Agent:** богатый контекст, multi-file write, применить/отклонить предложенные правки, run_terminal в подпапках с таймаутом, индексация по запросу.
- [x] **Проект с нуля:** создать папку из UI → агент пишет файлы и запускает команды.
- [ ] **Анализ:** многошаговый + граф зависимостей ✅ + Git ✅ + тесты.
- [x] **Improvement:** полный stack trace при retry, контекст ошибок (B5).

---

## Рекомендуемый порядок работ

1. **A2** Граф зависимостей (2–3 дня).
2. **B5** Контекст ошибок в Improvement (1 день).
3. **A3** Git-контекст в анализ (1 день).
4. **max_iterations** в конфиг (0.5 дня).
5. **C3.1** Свобода действий модели: tool run_project_analysis, убрать хардкод намерений во фронте (1–2 дня).
6. **A4** Покрытие тестами (1–2 дня).
7. **B6** Inline-редактирование (2–3 дня).
8. **C3** Стриминг улучшений (низкий приоритет).

---

## Файлы для изменений (по фазам)

| Фаза | Файлы |
|------|-------|
| A1 | `deep_analyzer.py` |
| A2 | Новый `dependency_graph.py`, `deep_analyzer.py` |
| A3 | `deep_analyzer.py`, git commands |
| B1 | `improvement_graph.py`, `use_case.py` (improvement) |
| B2 | `workflow/` (coder node), `improvement_graph.py` |
| B3 | `agent/tools.py`, `improvement/use_case.py`, API, UI: Improve форма + related_files |
| B4 | `chat/use_case.py`, `_build_messages` |
| B5 | `improvement_graph.py` |
| C1 | `agent/use_case.py`, `_build_initial_messages` |
| C2 | `agent/tool_parser.py`, `use_case.py` (подтверждение — backend) |
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
- **Тест `test_chat_code_returns_response`** падает без Ollama — рекомендуется мок LLM или skip при недоступности.
- **Хост Ollama в конфиге** — по умолчанию лучше `http://localhost:11434`, переопределение через development.toml / .env.
- **FileService._is_safe_path** — предпочтительно проверять через `relative_to(root)` вместо `startswith`.
- **Frontend: история в sync-чате** — исправлено (messagesRef для актуальной истории).
- **Container.reset()** — после reset кэш очищается, но `_config_override` остаётся (учитывать в тестах).

---

## Улучшения UI

**Высокий приоритет:** пустое состояние чата с подсказками; кнопка «Copy» на блоках кода; Escape закрывает модалки, фокус в поле ввода после отправки.

**Средний:** тосты (анимация, не перекрывать); ресайз панели чата и сайдбара; тултипы на иконках; единый индикатор «печатает»; кнопка отправки с подсказкой Enter/Shift+Enter.

**Низкий:** тёмная/светлая тема; моноширинный шрифт в редакторе; fade-in сообщений; командная палитра Cmd+K; доступность (aria-label, навигация с клавиатуры); мобильная версия.

**Порядок внедрения:** 1) пустое состояние + Copy на код; 2) Escape + фокус; 3) ресайз панели чата; 4) тултипы и тосты.

---

## Связанные документы

- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура: слои, потоки данных.
- [CHECKLIST.md](CHECKLIST.md) — ручная проверка по фазам (запуск, чат, workflow, RAG, IDE и т.д.).

В корне: [CONTRIBUTING.md](../CONTRIBUTING.md) — как вносить вклад.
