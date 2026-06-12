from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

_handlers: dict[str, logging.Logger] = {}


def get_job_logger(job_dir: Path, job_name: str = "") -> logging.Logger:
    key = str(job_dir.resolve())
    if key in _handlers:
        return _handlers[key]
    job_dir.mkdir(parents=True, exist_ok=True)
    log_path = job_dir / "job.log"
    logger = logging.getLogger(f"job.{job_name or job_dir.name}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
    _handlers[key] = logger
    return logger


def log_job(job_dir: Path, msg: str, level: str = "info") -> None:
    lg = get_job_logger(job_dir)
    getattr(lg, level, lg.info)(msg)


def read_job_log(job_dir: Path, tail: int = 80000) -> str:
    path = job_dir / "job.log"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-tail:]
