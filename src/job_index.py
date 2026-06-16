"""任务索引：SQLite 与文件系统双写。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .persistence import list_jobs as db_list, upsert_job


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_created(name: str, **meta: Any) -> None:
    upsert_job(name, status="pending", step="", created_at=_now(), updated_at=_now(), summary="")


def job_running(name: str, step: str = "") -> None:
    upsert_job(name, status="running", step=step, updated_at=_now())


def job_done(name: str, step: str = "完成", summary: str = "") -> None:
    upsert_job(name, status="done", step=step, updated_at=_now(), summary=summary)


def job_failed(name: str, error: str = "") -> None:
    upsert_job(name, status="error", step=error[:200], updated_at=_now())


def list_indexed_jobs(*, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return db_list(status=status, limit=limit)
