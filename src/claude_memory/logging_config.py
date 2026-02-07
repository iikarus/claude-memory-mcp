"""Structured logging configuration for production observability."""

import json
import logging
import os
import sys
from typing import Any


class JSONFormatter(logging.Formatter):
    """Log formatter that outputs JSON lines for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string."""
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_data["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data
        return json.dumps(log_data, default=str)


def configure_logging(level: str | None = None) -> None:
    """Configure logging for the application.

    Uses JSON format when LOG_FORMAT=json env var is set, otherwise human-readable.

    Args:
        level: Log level override. Defaults to LOG_LEVEL env var or INFO.
    """
    log_level = level or os.getenv("LOG_LEVEL") or "INFO"
    log_format = os.getenv("LOG_FORMAT", "text")

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplication
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root.addHandler(handler)
