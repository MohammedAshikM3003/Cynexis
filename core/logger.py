"""
CYNEXIS — Structured Logging
JSON-structured logging with console + rotating file output.
"""

import logging
import logging.handlers
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.config import settings, PROJECT_ROOT


class StructuredFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "event": getattr(record, "event", record.funcName),
            "message": record.getMessage(),
        }
        # Add metadata if present
        metadata = getattr(record, "metadata", None)
        if metadata:
            log_entry["metadata"] = metadata
        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


class ConsoleFormatter(logging.Formatter):
    """Human-readable colored console output."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        ts = datetime.now().strftime("%H:%M:%S")
        event = getattr(record, "event", "")
        event_str = f" [{event}]" if event else ""
        return (
            f"{color}{ts} {record.levelname:8s}{self.RESET} "
            f"{record.module}{event_str}: {record.getMessage()}"
        )


def setup_logging(level: str = "DEBUG") -> logging.Logger:
    """
    Initialize CYNEXIS structured logging.

    Returns the root CYNEXIS logger.
    """
    logger = logging.getLogger("cynexis")
    logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))

    # Prevent duplicate handlers on re-init
    if logger.handlers:
        return logger

    # Console handler (human readable)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(ConsoleFormatter())
    logger.addHandler(console)

    # File handler (structured JSON, rotating)
    log_dir = settings.resolve_path(settings.log_path)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "cynexis.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(StructuredFormatter())
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the cynexis namespace."""
    return logging.getLogger(f"cynexis.{name}")
