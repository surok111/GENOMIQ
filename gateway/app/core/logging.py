"""PHI-safe JSON logging.

Only technical fields belong in logs: correlation_id, task_id, status,
error_class, duration_ms. A deny-list processor is the backstop for anything
that still arrives nested inside an event.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

REDACTED = "[REDACTED]"

# Keys whose values are patient, specimen, or genomic input. Matched case-insensitively.
# `payload` and `result` are included because they wrap that data (queue body, FHIR Bundle).
PHI_DENY_KEYS = frozenset(
    {
        "patient_reference",
        "specimen_reference",
        "raw_data",
        "callback_url",
        "patient",
        "specimen",
        "payload",
        "result",
    }
)


def redact_phi(_logger: Any, _method: str, event_dict: structlog.typing.EventDict) -> structlog.typing.EventDict:
    """structlog processor: recursively replace deny-listed values with [REDACTED]."""
    redacted = _redact(event_dict)
    if isinstance(redacted, dict):
        return redacted
    return event_dict


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in PHI_DENY_KEYS:
                cleaned[key] = REDACTED
            else:
                cleaned[key] = _redact(item)
        return cleaned
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


def configure_logging() -> None:
    """Send structlog events to stdout as one JSON object per line."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_phi,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
