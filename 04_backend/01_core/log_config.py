"""Structured JSON logging setup for the tennetctl backend.

Call ``configure_logging()`` once at app startup. After that, all standard
``logging.getLogger(...)`` calls emit JSON lines to stdout.

JSON format (newline-delimited):
  {"ts": "2026-04-08T12:00:00.000Z", "level": "INFO", "logger": "...", "msg": "..."}

Env vars:
  LOG_LEVEL   default: INFO (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  LOG_FORMAT  default: json  (json | text — use text for local dev readability)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time


class _JsonFormatter(logging.Formatter):
    """Format log records as newline-delimited JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int((record.created % 1) * 1000):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Include any extra fields passed via `extra={}` on the log call.
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                try:
                    json.dumps(val)  # type-check: skip non-serialisable
                    payload[key] = val
                except (TypeError, ValueError):
                    payload[key] = str(val)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Install the JSON formatter on the root logger.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    root = logging.getLogger()
    if any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        return

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    fmt = os.environ.get("LOG_FORMAT", "json").lower()
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    # else: use Python's default text formatter for local dev

    root.addHandler(handler)
    root.setLevel(level)

    # Silence noisy third-party loggers
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
