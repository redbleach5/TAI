#!/usr/bin/env python3
"""Проверка сложных задач против запущенного API (http://localhost:8000).

Запустите сервер: python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000
Затем: python3 scripts/check_complex_tasks_live.py

Проверяет:
- POST /workflow — задача на код, ожидаем session_id, content, intent_kind, осмысленный контент
- POST /improve/run — улучшение run.py (docstring), ожидаем success/file_path/retries и при успехе proposed_full_content
- POST /chat — запрос на код, ожидаем content от модели
- GET /health — llm_available true
"""

import asyncio
import json
import sys
from pathlib import Path

# Корень проекта
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

BASE = "http://localhost:8000"
TIMEOUT = 120.0


async def main() -> None:
    ok = 0
    fail = 0

    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        # 1) Health
        print("1. GET /health")
        try:
            r = await client.get("/health")
            r.raise_for_status()
            data = r.json()
            assert data.get("llm_available") is True, "LLM должен быть доступен"
            print(f"   OK: llm_provider={data.get('llm_provider')}, llm_available={data.get('llm_available')}")
            ok += 1
        except Exception as e:
            print(f"   FAIL: {e}")
            fail += 1
            return  # без LLM дальше бессмысленно

        # 2) Workflow — задача на код
        print("\n2. POST /workflow (задача на код)")
        try:
            r = await client.post(
                "/workflow",
                json={"task": "Напиши функцию на Python: def add(a, b): return a + b"},
            )
            r.raise_for_status()
            data = r.json()
            assert "session_id" in data and "content" in data and "intent_kind" in data
            content = (data.get("content") or "").strip()
            assert len(content) > 20, "Ответ должен содержать осмысленный текст/код"
            print(f"   OK: session_id={data['session_id'][:8]}..., intent_kind={data['intent_kind']}, content_len={len(content)}")
            ok += 1
        except Exception as e:
            print(f"   FAIL: {e}")
            fail += 1

        # 3) Improve
        print("\n3. POST /improve/run (run.py, добавить docstring)")
        try:
            r = await client.post(
                "/improve/run",
                json={
                    "file_path": "run.py",
                    "issue": {"message": "Добавь однострочный docstring в начало файла"},
                    "auto_write": False,
                    "max_retries": 1,
                },
            )
            r.raise_for_status()
            data = r.json()
            assert "success" in data and "file_path" in data and "retries" in data
            assert data["file_path"] == "run.py"
            if data.get("success"):
                assert "proposed_full_content" in data or "validation_output" in data or "backup_path" in data
            print(f"   OK: success={data.get('success')}, retries={data.get('retries')}, has_proposed={bool(data.get('proposed_full_content'))}")
            ok += 1
        except Exception as e:
            print(f"   FAIL: {e}")
            fail += 1

        # 4) Chat — запрос на код
        print("\n4. POST /chat (запрос на код)")
        try:
            r = await client.post(
                "/chat",
                json={
                    "message": "Напиши функцию на Python: def square(n): return n * n",
                    "conversation_id": None,
                },
            )
            r.raise_for_status()
            data = r.json()
            content = (data.get("content") or "").strip()
            assert len(content) > 10
            print(f"   OK: content_len={len(content)}, model={data.get('model', '?')}")
            ok += 1
        except Exception as e:
            print(f"   FAIL: {e}")
            fail += 1

    print(f"\nИтого: {ok} OK, {fail} FAIL")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
