#!/usr/bin/env python3
"""Бенчмарк: удалённый Ollama + наш API.

Замеряет задержки (мс) по цепочке:
1) Прямой Ollama: GET /api/tags, POST /api/chat (короткий ответ)
2) Наш API (если запущен на localhost:8000): GET /health, GET /models, POST /chat

Использование:
  python3 scripts/benchmark_performance.py

Требует: конфиг с ollama host (config/default.toml + development.toml).
Опционально: запущенный бэкенд на http://localhost:8000 для замеров нашего API.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx


async def main() -> None:
    from src.infrastructure.config import load_config

    config = load_config()
    if config.llm.provider != "ollama":
        print(f"Конфиг: provider = {config.llm.provider}. Бенчмарк рассчитан на ollama.")
        sys.exit(0)

    host = config.ollama.host.rstrip("/")
    timeout = float(getattr(config.ollama, "timeout", 120) or 120)
    api_base = "http://localhost:8000"

    results: list[tuple[str, float, str]] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        # ---- 1) Прямой Ollama ----
        print("=== Прямые запросы к Ollama ===\n")

        t0 = time.perf_counter()
        try:
            r = await client.get(f"{host}/api/tags")
            r.raise_for_status()
        except Exception as e:
            print(f"GET /api/tags: ошибка — {e}")
        else:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(("Ollama GET /api/tags", elapsed, "ok"))
            print(f"  GET /api/tags: {elapsed:.0f} ms")

        try:
            model = config.models.get_models_for_provider("ollama").simple
        except Exception:
            model = "qwen2.5-coder:7b"
        t0 = time.perf_counter()
        try:
            r = await client.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Скажи одно слово: ок"}],
                    "stream": False,
                },
            )
            r.raise_for_status()
        except Exception as e:
            print(f"  POST /api/chat: ошибка — {e}")
        else:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(("Ollama POST /api/chat (1 слово)", elapsed, "ok"))
            print(f"  POST /api/chat (короткий ответ): {elapsed:.0f} ms")

        # ---- 2) Наш API (если доступен) ----
        print("\n=== Наш API (localhost:8000) ===\n")
        try:
            r = await client.get(f"{api_base}/health")
            r.raise_for_status()
        except Exception:
            print("  Бэкенд не запущен — пропуск замеров /health, /models, /chat")
        else:
            t0 = time.perf_counter()
            r = await client.get(f"{api_base}/health")
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(("API GET /health", elapsed, "ok"))
            print(f"  GET /health: {elapsed:.0f} ms")

            t0 = time.perf_counter()
            r = await client.get(f"{api_base}/models")
            r.raise_for_status()
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(("API GET /models", elapsed, "ok"))
            print(f"  GET /models: {elapsed:.0f} ms (включает list_models к Ollama)")

            # Сообщение, которое идёт в LLM (не шаблон приветствия)
            t0 = time.perf_counter()
            r = await client.post(
                f"{api_base}/chat",
                json={
                    "message": "Напиши одну строку кода на Python: x = 1 + 1",
                    "conversation_id": None,
                },
            )
            r.raise_for_status()
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(("API POST /chat (запрос в LLM)", elapsed, "ok"))
            print(f"  POST /chat (запрос в LLM): {elapsed:.0f} ms")

    # ---- Итог ----
    print("\n--- Итог (мс) ---")
    for name, ms, status in results:
        print(f"  {name}: {ms:.0f} ms ({status})")
    if results:
        ollama_chat = next((r for n, r, _ in results if "Ollama" in n and "chat" in n), None)
        api_chat = next((r for n, r, _ in results if "API" in n and "chat" in n), None)
        if ollama_chat and api_chat:
            overhead = api_chat - ollama_chat
            print(
                f"\n  Наценка нашего API на POST /chat (LLM): ~{overhead:.0f} ms "
                "(intent + model_selector/list_models + память + JSON)."
            )
    print(
        "\n--- Узкое место ---\n"
        "  Слабое место по задержкам — удалённый сервер Ollama (сеть + инференс).\n"
        "  POST /api/chat 400–600+ ms — это почти целиком ответ сервера; наш код добавляет десятки мс.\n"
        "  Подробнее: docs/PERFORMANCE.md"
    )


if __name__ == "__main__":
    asyncio.run(main())
