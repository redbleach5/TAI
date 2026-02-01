#!/usr/bin/env python3
"""Проверка использования GPU Ollama на удалённом хосте.

Читает host из конфига (config/default.toml + development.toml, OLLAMA_HOST).
Вызывает GET /api/ps — по size_vram видно, загружены ли модели в VRAM (GPU).
Если size_vram > 0 у загруженных моделей — Ollama использует GPU.
Если нет моделей в памяти или size_vram == 0 — возможна работа на CPU; см. docs/OLLAMA_GPU.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx


def main() -> None:
    from src.infrastructure.config import load_config

    config = load_config()
    if config.llm.provider != "ollama":
        print(f"Конфиг: provider = {config.llm.provider}, ожидался ollama. Выход.")
        sys.exit(0)

    host = config.ollama.host.rstrip("/")
    print(f"Ollama host: {host}\n")

    with httpx.Client(timeout=10.0) as http:
        # Список загруженных в память моделей (в т.ч. VRAM)
        print("--- GET /api/ps (загруженные модели, VRAM) ---")
        try:
            r = http.get(f"{host}/api/ps")
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"Ошибка запроса /api/ps: {e}")
            print("Проверьте доступность хоста и что Ollama запущен.")
            sys.exit(1)

        models_loaded = data.get("models") or []
        if not models_loaded:
            print("В памяти нет загруженных моделей (ничего не запущено после последнего запроса).")
            print("Сделайте один запрос к чату/генерации, затем снова запустите этот скрипт.")
            print("\nЕсли после запроса здесь по-прежнему пусто или size_vram = 0 — на сервере Ollama")
            print("вероятно используется только CPU. См. docs/OLLAMA_GPU.md (nvidia-smi, логи, OLLAMA_NUM_GPU).")
            sys.exit(0)

        for m in models_loaded:
            name = m.get("name") or m.get("model") or "?"
            size_vram = m.get("size_vram") or 0
            size_vram_mb = size_vram // (1024 * 1024) if size_vram else 0
            if size_vram and size_vram > 0:
                print(f"  {name}: size_vram = {size_vram_mb} MiB — используется GPU (VRAM).")
            else:
                print(f"  {name}: size_vram = 0 — модель может работать на CPU.")
        print()
        print("Если у всех моделей size_vram = 0 при активных запросах — на сервере Ollama")
        print("включите GPU: см. docs/OLLAMA_GPU.md (OLLAMA_NUM_GPU, CUDA_VISIBLE_DEVICES, логи).")


if __name__ == "__main__":
    main()
