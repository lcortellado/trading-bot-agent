"""
Structured logging setup.
Uses standard library logging with a consistent format across all modules.
Import `get_logger` wherever a logger is needed.
"""
import logging
import sys
from typing import Any


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_configured = False


def configure_logging(debug: bool = False) -> None:
    """Call once at application startup."""
    global _configured
    if _configured:
        return

    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Pass __name__ from the calling module."""
    return logging.getLogger(name)


class DecisionLogger:
    """
    Helper to log trade decisions with mandatory reasoning (required by CLAUDE.md).
    Every enter/skip decision must explain why.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._log = logger

    def enter(self, symbol: str, reason: str, **context: Any) -> None:
        self._log.info(
            "DECISION=ENTER | symbol=%s | reason=%s | %s",
            symbol,
            reason,
            " | ".join(f"{k}={v}" for k, v in context.items()),
        )

    def skip(self, symbol: str, reason: str, **context: Any) -> None:
        self._log.info(
            "DECISION=SKIP   | symbol=%s | reason=%s | %s",
            symbol,
            reason,
            " | ".join(f"{k}={v}" for k, v in context.items()),
        )
