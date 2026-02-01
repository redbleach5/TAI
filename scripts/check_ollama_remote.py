#!/usr/bin/env python3
"""Проверка подключения к удалённому Ollama: список моделей и тестовый запрос chat."""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx


async def main() -> None:
    from src.infrastructure.config import load_config

    config = load_config()
    if config.llm.provider != "ollama":
        print(f"Конфиг: provider = {config.llm.provider}, ожидался ollama. Проверка Ollama пропущена.")
        return

    host = config.ollama.host.rstrip("/")
    timeout = getattr(config.ollama, "timeout", 120) or 30
    print(f"Ollama host из конфига: {host}")
    print(f"Timeout: {timeout}s")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1) Список моделей: GET /api/tags
        print("\n--- GET /api/tags (список моделей) ---")
        try:
            r = await client.get(f"{host}/api/tags")
            r.raise_for_status()
            data = r.json()
            models = data.get("models") or []
            print(f"OK, статус {r.status_code}. Моделей: {len(models)}")
            for m in models[:10]:
                name = m.get("name") or m.get("model") or str(m)
                print(f"  - {name}")
            if len(models) > 10:
                print(f"  ... и ещё {len(models) - 10}")
        except httpx.HTTPError as e:
            print(f"Ошибка: {e}")
            return
        except Exception as e:
            print(f"Ошибка: {e}")
            return

        # 2) Тестовый chat: POST /api/chat
        model = (config.models.get_models_for_provider("ollama").simple if hasattr(config, "models") else None) or "qwen2.5-coder:7b"
        print(f"\n--- POST /api/chat (модель: {model}) ---")
        try:
            r = await client.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Ответь одним словом: привет"}],
                    "stream": False,
                },
                timeout=float(timeout),
            )
            r.raise_for_status()
            data = r.json()
            msg = (data.get("message") or {})
            content = msg.get("content", "")
            print(f"OK, статус {r.status_code}. Ответ: {content[:200]!r}")
        except httpx.HTTPStatusError as e:
            print(f"HTTP ошибка: {e.response.status_code} - {e.response.text[:300]}")
        except httpx.TimeoutException:
            print("Таймаут запроса к /api/chat")
        except Exception as e:
            print(f"Ошибка: {e}")

    print("\nПроверка завершена.")


if __name__ == "__main__":
    asyncio.run(main())
