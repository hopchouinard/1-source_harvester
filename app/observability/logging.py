from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Minimal logging setup; Phase J will provide structlog/loguru JSON config."""
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

