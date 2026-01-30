# Фаза 1: Chat режим — план реализации

**Критерий готовности:** Пользователь может отправить сообщение и получить ответ в UI.

---

## 1. Backend

### 1.1 ChatUseCase (`src/application/chat/`)

- **use_case.py** — `ChatUseCase`:
  - Вход: `message: str`, опционально `history: list[LLMMessage]`
  - Вызов LLM через `LLMPort.generate()`
  - Модель: пока фиксированная `config.models.simple` (Model Router в Фазе 2)
  - Выход: `ChatResponse(content: str, model: str)`

- **dto.py** — Pydantic-модели:
  - `ChatRequest(message: str, history?: list)`
  - `ChatResponse(content: str, model: str)`

### 1.2 IntentDetector (`src/domain/services/`)

- **intent_detector.py** — эвристика без LLM:
  - `detect(message: str) -> Intent` (GREETING | HELP | CHAT)
  - Greeting: "привет", "hello", "hi" → шаблонный ответ
  - Help: "помощь", "help", "?" → шаблонный ответ
  - Иначе → CHAT (идём в LLM)

### 1.3 API routes (`src/api/routes/`)

- **chat.py**:
  - `POST /chat` — sync, возвращает `ChatResponse`
  - `GET /chat/stream` — SSE, стримит chunks (опционально в Фазе 1)

- Подключить роуты в `src/main.py` через `app.include_router()`

### 1.4 Dependencies

- Добавить `get_chat_use_case()` в `dependencies.py` — зависит от `get_ollama_adapter()`, `get_config()`

---

## 2. Frontend

### 2.1 API client (`frontend/src/api/`)

- `postChat(message: string, history?: Message[]): Promise<ChatResponse>`
- `useChatStream(message: string)` — hook для SSE (если реализуем stream в Фазе 1)

### 2.2 Chat feature (`frontend/src/features/chat/`)

- **ChatInput.tsx** — поле ввода + кнопка Send
- **ChatMessage.tsx** — отображение сообщения (user/assistant)
- **ChatPanel.tsx** — список сообщений + input, состояние `messages`
- **useChat.ts** — хук: отправка, получение ответа, обновление истории

### 2.3 Интеграция в App

- Заменить placeholder в `App.tsx` на `ChatPanel`
- Сохранить `HealthStatus` в header

---

## 3. Порядок реализации

1. **DTO + ChatUseCase** — без API, unit-тест
2. **IntentDetector** — unit-тест
3. **API route POST /chat** — integration test
4. **Frontend API client** — `postChat`
5. **ChatPanel + useChat** — UI
6. **SSE /chat/stream** (опционально) — если время есть

---

## 4. Зависимости (уже есть)

- `LLMPort` — реализован в `OllamaAdapter`
- `get_config()` — `config.models.simple` для выбора модели
- `OllamaAdapter.generate()` — sync вызов

---

## 5. Файлы для создания

```
src/application/chat/
  __init__.py
  use_case.py
  dto.py

src/domain/services/
  __init__.py
  intent_detector.py

src/api/routes/
  chat.py

frontend/src/api/
  client.ts  (дополнить postChat)

frontend/src/features/chat/
  ChatInput.tsx
  ChatMessage.tsx
  ChatPanel.tsx
  useChat.ts
```
