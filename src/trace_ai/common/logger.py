import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# ── MDC context (per-request, thread + async safe) ────────────────────────────
_mdc: ContextVar[dict[str, Any]] = ContextVar("mdc", default={})


def set_context(**kwargs: Any) -> None:
    """Merge kwargs into the current MDC context."""
    _mdc.set({**_mdc.get(), **kwargs})


def clear_context() -> None:
    """Clear all MDC fields — call at the end of each pipeline run."""
    _mdc.set({})


def get_context() -> dict[str, Any]:
    """Return a copy of the current MDC context — useful for tests."""
    return dict(_mdc.get())


# ── JSON formatter ────────────────────────────────────────────────────────────
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            **_mdc.get(),                               # MDC fields — contract_id, stage, request_id etc.
            **record.__dict__.get("extra_fields", {}),  # per-call kwargs
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


# ── Logger setup ──────────────────────────────────────────────────────────────
def _build_logger() -> logging.Logger:
    from trace_ai.config import config

    logger = logging.getLogger("trace_ai")
    if logger.handlers:
        return logger

    formatter = _JsonFormatter()

    # stdout handler — always active
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # rotating file handler — only when LOG_TO_FILE=true
    if config.LOG_TO_FILE:
        log_path = Path(config.LOG_FILE_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=config.LOG_FILE_MAX_BYTES,
            backupCount=config.LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    logger.propagate = False
    return logger


_logger: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = _build_logger()
    return _logger


# ── Public API ────────────────────────────────────────────────────────────────
def log(message: str, severity: str = "INFO", **kwargs: Any) -> None:
    """
    Emit a structured JSON log line to stdout and optionally to a rotating log file.

    MDC fields (contract_id, stage, request_id) are injected automatically
    from context — no need to pass them on every call.

    Extra per-call fields are passed as kwargs:
        log("DLP complete", pii_types=["SSN"], findings_count=3)
    """
    level = getattr(logging, severity.upper(), logging.INFO)
    _get_logger().log(level, message, extra={"extra_fields": kwargs})
