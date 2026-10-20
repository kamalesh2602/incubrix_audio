import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable tracking correlation ID across asynchronous request contexts
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Returns the correlation ID for the current async context."""
    return correlation_id_ctx.get()


def set_correlation_id(correlation_id: Optional[str]) -> None:
    """Sets the correlation ID for the current async context."""
    correlation_id_ctx.set(correlation_id)


class JSONLogFormatter(logging.Formatter):
    """Formats log records as structured, single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id() or getattr(record, "correlation_id", None),
        }

        # Include caller code coordinates if available
        if record.pathname:
            log_obj["location"] = f"{record.filename}:{record.lineno}"

        # Include exception traceback if present
        if record.exc_info:
            log_obj["exception"] = "".join(traceback.format_exception(*record.exc_info)).strip()

        # Include extra custom fields if attached
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "correlation_id",
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in standard_attrs and not k.startswith("_")}
        if extras:
            log_obj["extra"] = extras

        return json.dumps(log_obj, default=str)


def setup_logging(log_level: str = "INFO") -> None:
    """Configures structured JSON logging on root and framework loggers."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONLogFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers to prevent duplicate lines
    root_logger.handlers = [handler]

    # Configure uvicorn loggers
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        l = logging.getLogger(logger_name)
        l.handlers = [handler]
        l.propagate = False
