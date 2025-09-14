from __future__ import annotations

import json
import logging

import structlog

from app.observability.logging import configure_logging


def test_structlog_json_and_redaction(capsys):
    configure_logging(debug=True)
    log = structlog.get_logger("test")
    log.info("event", api_key="sk-123", token="abc", value=42)
    captured = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(captured)
    assert data["event"] == "event"
    assert data["api_key"] == "***"
    assert data["token"] == "***"
    assert data["value"] == 42

