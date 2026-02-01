# Веб-поиск (@web)

Реализация по образцу **Cherry Studio**: несколько источников поиска — SearXNG, Brave, Tavily и **Google Custom Search**.

## Источники

- **DuckDuckGo** — всегда используется (HTML API, без ключа).
- **SearXNG** — свой URL или публичные инстансы (см. ниже).
- **Brave Search** — при наличии `BRAVE_API_KEY` (2000 запросов/мес бесплатно).
- **Tavily** — при наличии `TAVILY_API_KEY` (ключ на [app.tavily.com](https://app.tavily.com)).
- **Google Custom Search** — при наличии `GOOGLE_API_KEY` и `GOOGLE_CX` (100 запросов/день бесплатно).

Все включённые движки вызываются **параллельно**, результаты объединяются и дедуплицируются.

## Настройка

### 1. Через Настройки в UI

В разделе **Настройки → Веб-поиск (@web)**:

- **SearXNG URL** — пусто = используются публичные инстансы; иначе свой URL (например `http://localhost:8080`).
- **Brave API Key** — опционально; получить на [brave.com/search/api](https://brave.com/search/api).
- **Tavily API Key** — опционально; зарегистрироваться на [app.tavily.com](https://app.tavily.com), получить ключ и при необходимости настроить 2FA.
- **Google API Key** и **Google Search Engine ID (cx)** — опционально; 100 запросов/день бесплатно (см. раздел Google ниже).

Значения сохраняются в `config/development.toml`.

### 2. Через переменные окружения

Переменные переопределяют конфиг из файла:

- `SEARXNG_URL` — URL своего инстанса SearXNG.
- `BRAVE_API_KEY` — ключ Brave Search API.
- `TAVILY_API_KEY` — ключ Tavily API.
- `GOOGLE_API_KEY` — ключ Google Custom Search JSON API (Google Cloud).
- `GOOGLE_CX` — ID поисковой машины (Programmable Search Engine).

Пример в `.env`:

```env
SEARXNG_URL=http://localhost:8080
BRAVE_API_KEY=...
TAVILY_API_KEY=...
GOOGLE_API_KEY=...
GOOGLE_CX=...
```

## Локальный SearXNG (по документации Cherry Studio)

SearXNG — открытый мета-поисковик, можно развернуть у себя и не зависеть от публичных инстансов.

### Быстрый запуск (Docker)

1. Установить [Docker](https://www.docker.com/).
2. Запустить образ, например на порту 8080:
   ```bash
   docker run -d -p 8080:8080 searxng/searxng:latest
   ```
3. Для работы с нашим бэкендом у инстанса должен быть включён **JSON-формат**. В официальном образе SearXNG JSON уже поддерживается по умолчанию (запрос к `/search?format=json`).
4. В настройках приложения указать **SearXNG URL**: `http://localhost:8080` (или `http://host.docker.internal:8080`, если бэкенд в Docker).

### Развёртывание на сервере (docker-compose)

Клонировать [searxng-docker](https://github.com/searxng/searxng-docker) и в `searxng/settings.yml` добавить в `search.formats` значение `json` (если его ещё нет). Для доступа извне рекомендуется настроить Nginx с HTTP Basic Auth (см. [документацию Cherry Studio — SearXNG](https://docs.cherry-ai.com/docs/en-us/websearch/searxng)).

## Google Custom Search (как в Cherry Studio)

1. Создать проект в [Google Cloud Console](https://console.cloud.google.com/) и включить **Custom Search API**.
2. Создать API-ключ (Credentials → Create credentials → API key).
3. Создать поисковую машину на [programmablesearchengine.google.com](https://programmablesearchengine.google.com/): «Search the entire web» — чтобы искать по всему интернету.
4. Скопировать **Search engine ID** (cx) и **API key**, указать в Настройки → Веб-поиск или в переменных `GOOGLE_API_KEY` и `GOOGLE_CX`.

Бесплатный лимит: 100 запросов в день. Оба параметра (API key и cx) обязательны.

## Tavily

1. Регистрация на [app.tavily.com](https://app.tavily.com).
2. После регистрации может потребоваться 2FA (например через приложение Tencent Authenticator в WeChat или Microsoft Authenticator).
3. Скопировать API key и вставить в Настройки → Веб-поиск → Tavily API Key или в переменную `TAVILY_API_KEY`.

## Использование в чате

В сообщении указать `@web` и запрос, например:

- `@web python asyncio tutorial`
- `@web последние новости OpenAI`

Если ни один движок не вернул результатов, пользователь увидит сообщение о временной недоступности веб-поиска (без вызова модели).
