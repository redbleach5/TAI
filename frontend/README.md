# CodeGen AI — Frontend

React + TypeScript + Vite. Подключается к backend на порту 8000.

## Запуск

```bash
npm install
npm run dev
```

Открыть http://localhost:5173

## Сборка

```bash
npm run build
```

## Структура

```
src/
├── api/           client.ts — fetch, SSE
├── features/
│   ├── chat/      ChatPanel, ChatInput, ChatMessage, useChat
│   ├── health/    HealthStatus
│   ├── ide/       IDEPanel, WorkflowCodeContext (Copy, Download)
│   ├── layout/    Layout (chat / workflow / ide / split)
│   └── workflow/  WorkflowPanel, useWorkflowStream
```

## API

Backend по умолчанию: `/api` (прокси в dev) или `VITE_API_URL`.

- `POST /chat` — chat sync
- `GET /chat/stream` — chat SSE
- `POST /workflow` — workflow sync
- `POST /workflow?stream=true` — workflow SSE
- `GET /health` — статус LLM
