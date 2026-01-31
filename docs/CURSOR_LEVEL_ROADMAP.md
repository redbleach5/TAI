# План выхода на уровень Cursor AI: анализ и написание кода

## Текущее состояние

| Область | Реализовано | Пробелы |
|---------|-------------|---------|
| **Анализ** | DeepAnalyzer: многошаговость (A1), RAG 8 запросов, targeted RAG | Граф зависимостей, Git |
| **Чат** | context_files, @rag, @web, @code | Авто-RAG по запросу |
| **Agent** | read_file, write_file (multi-file B3), search_rag, run_terminal, list_files | — |
| **Improvement** | plan → code → validate → retry, RAG, related_files (B3) | — |
| **Workflow** | planner → researcher → tests → coder | RAG по task, без project_map |

---

## Часть 1: Анализ уровня Cursor

### Phase A1: Многошаговый анализ (приоритет: высокий)
- [x] Шаг 1: LLM получает статику + ключевые файлы → выделяет 3–5 проблемных модулей
- [x] Шаг 2: RAG по каждому модулю (targeted search) → углублённый контекст
- [x] Шаг 3: LLM финальный синтез с приоритетами
- [x] Fallback: если токены/время — один проход как сейчас

### Phase A2: Граф зависимостей (приоритет: средний)
- [ ] Парсер импортов: Python (ast), TypeScript/JS (regex)
- [ ] Построение графа: модуль → импорты
- [ ] Выявление: циклические зависимости, неиспользуемые импорты
- [ ] Добавить в промпт анализа: "Зависимости: A→B→C, цикл в X"

### Phase A3: Git-контекст (приоритет: средний)
- [ ] Недавние изменения: `git log -5 --name-only`
- [ ] Часто меняющиеся файлы: `git log --follow --format= --name-only | sort | uniq -c`
- [ ] Добавить в промпт: "Недавно изменено: X, Y. Часто меняется: Z"

### Phase A4: Покрытие тестами (приоритет: низкий)
- [ ] Интеграция pytest-cov / coverage: какие файлы покрыты
- [ ] Добавить в промпт: "Без тестов: A, B. Низкое покрытие: C"

---

## Часть 2: Написание кода уровня Cursor

### Phase B1: RAG в Improvement (приоритет: высокий)
- [x] При improve_file: RAG search по file_path + issue
- [x] Добавить в plan/code промпт: релевантные чанки (вызовы, аналоги)
- [x] Учёт: как этот файл вызывается, какие паттерны в проекте

### Phase B2: Project map в генерацию кода (приоритет: высокий)
- [x] Workflow coder: получает project_map (структура, классы, функции)
- [x] Improvement: получает project_map для контекста стиля
- [x] Промпт: "Следуй структуре проекта: ..."

### Phase B3: Multi-file edits (приоритет: высокий)
- [x] Agent: поддержка write_file для нескольких файлов за один ответ
- [x] Improvement: опция "затронуть связанные файлы" (импорты, тесты)
- [x] API: `improve_file` принимает `related_files: list[str]`

### Phase B4: Авто-RAG в чат (приоритет: средний)
- [x] При отправке сообщения: автоматический RAG search по запросу
- [x] Инжектировать топ-5 чанков в контекст (если не @rag явно)
- [x] Настраиваемо: вкл/выкл в настройках

### Phase B5: Контекст ошибок (приоритет: средний)
- [ ] Improvement: при retry — полный stack trace + файлы из traceback
- [ ] RAG по сообщению ошибки: найти похожие исправления
- [ ] Промпт: "Ошибка в X:line N. Похожий код в проекте: ..."

### Phase B6: Inline-редактирование (приоритет: низкий)
- [ ] Выделение в редакторе → "улучшить выделенное"
- [ ] Diff preview перед применением
- [ ] Поддержка partial edits (только выделенные строки)

---

## Часть 3: Agent и UX

### Phase C1: Agent — лучший контекст (приоритет: высокий)
- [x] При старте: автоматически search_rag по запросу пользователя
- [x] Инжектировать project_map в system prompt (первые 2K символов)
- [x] read_file: при чтении — предлагать связанные (по импортам)

### Phase C2: Agent — multi-file write (приоритет: средний)
- [x] Парсинг нескольких `<tool_call>` write_file в одном ответе
- [ ] Batch write с подтверждением: "Записать 3 файла?" (требует backend)

### Phase C3: Streaming улучшений (приоритет: низкий)
- [ ] Improvement: стриминг plan → code по мере генерации
- [ ] UI: показывать план, затем код в реальном времени

---

## Порядок реализации (рекомендуемый)

| # | Фаза | Оценка | Зависимости |
|---|------|--------|-------------|
| 1 | B1 RAG в Improvement | 1–2 дня | — |
| 2 | B2 Project map в генерацию | 0.5 дня | — |
| 3 | B4 Авто-RAG в чат | 0.5 дня | — |
| 4 | C1 Agent — лучший контекст | 1 день | — |
| 5 | A1 Многошаговый анализ | 2–3 дня | — |
| 6 | B3 Multi-file edits | 2 дня | Agent tools |
| 7 | A2 Граф зависимостей | 2–3 дня | — |
| 8 | B5 Контекст ошибок | 1 день | — |
| 9 | A3 Git-контекст | 1 день | — |
| 10 | C2 Agent multi-file write | 1 день | C1 |
| 11 | A4 Покрытие тестами | 1–2 дня | pytest-cov |
| 12 | B6 Inline-редактирование | 2–3 дня | Frontend |

---

## Критерии "уровня Cursor"

- [ ] Анализ: многошаговый, с графом зависимостей, Git, тестами
- [ ] Генерация: RAG + project_map в контексте, multi-file
- [ ] Чат: авто-RAG по запросу
- [ ] Agent: богатый контекст, multi-file write
- [ ] Improvement: RAG, полный stack trace при retry

---

## Файлы для изменений

| Фаза | Файлы |
|------|-------|
| B1 | `improvement_graph.py`, `use_case.py` (improvement) |
| B2 | `workflow/` (coder node), `improvement_graph.py` |
| B4 | `chat/use_case.py`, `_build_messages` |
| C1 | `agent/use_case.py`, `_build_initial_messages` |
| A1 | `deep_analyzer.py` |
| B3 | `agent/tools.py`, `improvement/use_case.py`, API, **UI**: Improve форма + related_files |
| A2 | Новый `dependency_graph.py`, `deep_analyzer.py` |
| B5 | `improvement_graph.py` |
| A3 | `deep_analyzer.py`, git commands |
| C2 | `agent/tool_parser.py`, `use_case.py` (парсинг готов, подтверждение — backend) |
