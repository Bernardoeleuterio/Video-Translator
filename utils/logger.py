"""Logging setup for the application."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"


def setup_logging() -> None:
    """Configure console and rotating file logs."""

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(threadName)s | %(message)s"
        )
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.handlers.clear()
        root.addHandler(file_handler)
        root.addHandler(console_handler)
    except Exception:
        logging.basicConfig(level=logging.INFO)
        logging.exception("Falha ao configurar logs em arquivo.")
