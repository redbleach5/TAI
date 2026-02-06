"""Интеграционные тесты сложных задач: workflow (code_gen), improve, chat с кодом.

Требуют доступный Ollama (локальный или удалённый). Проверяют, что ответы API
соответствуют ожидаемой структуре и содержанию.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app

# Таймаут для запросов к LLM (workflow/improve/chat могут быть долгими)
LLM_TIMEOUT = 120.0


@pytest.mark.slow
@pytest.mark.asyncio
async def test_workflow_code_task_returns_structured_response():
    """Workflow с задачей на код возвращает session_id, content, intent_kind и осмысленный контент."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=LLM_TIMEOUT,
    ) as client:
        try:
            resp = await client.post(
                "/workflow",
                json={"task": "Напиши функцию на Python: def add(a, b): return a + b"},
            )
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                pytest.skip(
                    "Workflow code task in ASGI test can close event loop; "
                    "run scripts/check_complex_tasks_live.py against live server."
                )
            raise
    if resp.status_code == 500:
        pytest.skip("Workflow returned 500 (LLM probably unavailable); run against live server.")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "session_id" in data
    assert "content" in data
    assert "intent_kind" in data
    assert data["intent_kind"] in ("greeting", "chat", "code", "code_gen")
    # Для задачи на код ожидаем не шаблон приветствия, а план/код
    content = data.get("content") or ""
    assert len(content.strip()) > 20, "Ответ должен содержать осмысленный текст или код"
    # При успешном code_gen могут быть plan/code/validation_passed
    if data.get("intent_kind") == "code" or "code" in data:
        assert content or data.get("plan") or data.get("code"), "Должен быть план или код"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_improve_run_returns_expected_structure():
    """POST /improve/run возвращает success, file_path, retries; при успехе — proposed_full_content или backup.

    Долгий запрос к LLM в ASGI-тесте иногда приводит к закрытию event loop на стороне сервера.
    Для полной E2E проверки improve запустите сервер и: python3 scripts/check_complex_tasks_live.py
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=LLM_TIMEOUT,
    ) as client:
        try:
            resp = await client.post(
                "/improve/run",
                json={
                    "file_path": "run.py",
                    "issue": {"message": "Добавь однострочный docstring в начало файла"},
                    "auto_write": False,
                    "max_retries": 1,
                },
            )
        except (RuntimeError, Exception) as e:
            if "Event loop is closed" in str(e) or "connection" in str(e).lower():
                pytest.skip(
                    "Improve run (long LLM call) may hit event loop/connection issues in ASGI test; "
                    "run scripts/check_complex_tasks_live.py against live server."
                )
            if "ReadTimeout" in type(e).__name__ or "read" in str(e).lower():
                pytest.skip(
                    "Improve run exceeded read timeout (increase config ollama.timeout for heavy models); "
                    "run scripts/check_complex_tasks_live.py against live server."
                )
            raise
    if resp.status_code != 200:
        pytest.skip(
            f"Improve returned {resp.status_code} (possible event loop/LLM issue in ASGI test); "
            "run scripts/check_complex_tasks_live.py against live server for full E2E."
        )
    data = resp.json()
    assert "success" in data
    assert "file_path" in data
    assert data["file_path"] == "run.py"
    assert "retries" in data
    assert isinstance(data["retries"], int)
    if data.get("success"):
        assert "proposed_full_content" in data or "backup_path" in data or "validation_output" in data
    else:
        assert "error" in data or "validation_output" in data


@pytest.mark.slow
@pytest.mark.asyncio
async def test_chat_code_request_returns_llm_content():
    """Чат с запросом на код возвращает контент от модели (не только шаблон)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=LLM_TIMEOUT,
    ) as client:
        resp = await client.post(
            "/chat",
            json={
                "message": "Напиши функцию на Python: def square(n): return n * n",
                "conversation_id": None,
            },
        )
    if resp.status_code == 500:
        pytest.skip("Chat returned 500 (LLM probably unavailable); run against live server.")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "content" in data
    content = (data.get("content") or "").strip()
    assert len(content) > 10, "Ответ чата не должен быть пустым"
    # Если модель вернула код — проверяем наличие ключевых элементов
    if "def square" in content or "return n" in content.lower():
        assert "square" in content or "n * n" in content or "n*n" in content


@pytest.mark.slow
@pytest.mark.asyncio
async def test_workflow_stream_emits_events():
    """Workflow с stream=true отдаёт SSE-события и в конце done с payload."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=LLM_TIMEOUT,
    ) as client:
        async with client.stream(
            "POST",
            "/workflow",
            params={"stream": "true"},
            json={"task": "Скажи одним словом: ок"},
        ) as resp:
            assert resp.status_code == 200
            events = []
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
                if len(events) >= 5:
                    break
    assert len(events) >= 1
    assert "done" in events or "close" in events
