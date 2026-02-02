"""Structured logging setup with stdlib integration."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog


def setup_logging(
    level: str = "INFO",
    file_path: str = "",
    rotation_max_mb: int = 5,
    rotation_backups: int = 3,
) -> None:
    """Configure structlog integrated with standard library logging.

    Both structlog.get_logger() and logging.getLogger() outputs are formatted
    consistently. Level from config is applied to all loggers.

    If file_path is set, logs are also written to that file with rotation
    (when file exceeds rotation_max_mb, it is rotated; up to rotation_backups
    backup files are kept). Directory is created if missing.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    use_json = level.upper() != "DEBUG"

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    if use_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()

    # Always log to stdout (terminal)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(log_level)
    root.addHandler(stream_handler)

    # Optionally log to file with rotation
    if file_path and file_path.strip():
        path = Path(file_path.strip()).resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                path,
                maxBytes=rotation_max_mb * 1024 * 1024,
                backupCount=rotation_backups,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            root.addHandler(file_handler)
        except OSError as e:
            # Fallback: log to stderr that file logging failed, keep stdout only
            sys.stderr.write(f"Log file disabled: could not open {path}: {e}\n")
