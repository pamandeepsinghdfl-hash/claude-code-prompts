"""Structured logging + per-run JSON report writer.

Every factory run gets its own log file under `logs/YYYY-MM-DD/` so it's
trivial to inspect what was published, where it came from, and the
copyright safety scores for each piece of source material.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def setup_logger(level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_dir = Path(log_dir) / today
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / "factory.log"
    logger = logging.getLogger("shorts_factory")
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.propagate = False
    return logger


class RunReport:
    """Accumulates a JSON summary of one full daily run."""

    def __init__(self, log_dir: str = "logs"):
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.log_dir = Path(log_dir) / datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.shorts: list[Dict[str, Any]] = []
        self.errors: list[str] = []

    def add_short(self, payload: Dict[str, Any]) -> None:
        self.shorts.append(payload)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def write(self) -> Path:
        out = self.log_dir / "report.json"
        out.write_text(
            json.dumps(
                {
                    "started_at": self.started_at,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "shorts_count": len(self.shorts),
                    "shorts": self.shorts,
                    "errors": self.errors,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return out
