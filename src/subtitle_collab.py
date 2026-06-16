"""实时协作字幕校对：segment 编辑锁。"""

from __future__ import annotations

import time
from typing import Any

_locks: dict[str, dict[int, dict[str, Any]]] = {}
_LOCK_TTL = 120


def acquire_lock(job: str, index: int, user: str) -> dict[str, Any]:
  now = time.time()
  job_locks = _locks.setdefault(job, {})
  existing = job_locks.get(index)
  if existing and existing["user"] != user and now - existing["ts"] < _LOCK_TTL:
    return {"ok": False, "held_by": existing["user"]}
  job_locks[index] = {"user": user, "ts": now}
  return {"ok": True}


def release_lock(job: str, index: int, user: str) -> None:
  job_locks = _locks.get(job, {})
  if job_locks.get(index, {}).get("user") == user:
    job_locks.pop(index, None)


def list_locks(job: str) -> dict[int, str]:
  now = time.time()
  job_locks = _locks.get(job, {})
  return {i: v["user"] for i, v in job_locks.items() if now - v["ts"] < _LOCK_TTL}
