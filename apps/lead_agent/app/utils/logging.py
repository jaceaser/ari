"""
Structured logging. Outputs JSON lines to stdout for Azure App Insights ingestion.
"""
from __future__ import annotations

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
        stream=sys.stdout,
        level=level,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
