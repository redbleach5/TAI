#!/usr/bin/env python3
"""Run the application."""
import uvicorn

from src.api.dependencies import get_config

if __name__ == "__main__":
    config = get_config()
    uvicorn.run(
        "src.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=True,
    )
