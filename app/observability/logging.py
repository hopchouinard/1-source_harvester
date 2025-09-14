from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


SENSITIVE_KEYS = {"api_key", "apikey", "authorization", "token", "secret", "password"}


def _redact_sensitive(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for k in list(event_dict.keys()):
        lk = k.lower().replace("-", "_")
        if any(s in lk for s in SENSITIVE_KEYS):
            event_dict[k] = "***"
    return event_dict


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, stream=sys.stdout)
    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        _redact_sensitive,
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

