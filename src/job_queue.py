from __future__ import annotations

import threading
from collections import deque
from typing import Any

_lock = threading.Lock()
_cond = threading.Condition(_lock)
_max_concurrent = 1
_active_jobs: dict[str, str] = {}
_waiting_queue: deque[str] = deque()
_job_status: dict[str, str] = {}


def configure(max_concurrent: int = 1) -> None:
    global _max_concurrent
    _max_concurrent = max(1, max_concurrent)


def enqueue(job_name: str) -> int:
    with _cond:
        if job_name not in _waiting_queue and job_name not in _active_jobs:
            _waiting_queue.append(job_name)
            _job_status[job_name] = "queued"
        try:
            return list(_waiting_queue).index(job_name) + 1
        except ValueError:
            return 0


def acquire(job_name: str, on_wait: Any = None) -> None:
    """阻塞直到轮到该任务且有空闲 GPU 槽位。"""
    with _cond:
        if job_name not in _waiting_queue and job_name not in _active_jobs:
            _waiting_queue.append(job_name)
        while True:
            at_front = bool(_waiting_queue) and _waiting_queue[0] == job_name
            has_slot = len(_active_jobs) < _max_concurrent
            if at_front and has_slot:
                if _waiting_queue and _waiting_queue[0] == job_name:
                    _waiting_queue.popleft()
                _active_jobs[job_name] = "running"
                _job_status[job_name] = "running"
                return
            _job_status[job_name] = "queued"
            if on_wait:
                try:
                    pos = list(_waiting_queue).index(job_name) + 1 if job_name in _waiting_queue else 0
                    on_wait(pos)
                except Exception:
                    pass
            _cond.wait()


def release(job_name: str) -> None:
    with _cond:
        _active_jobs.pop(job_name, None)
        _job_status.pop(job_name, None)
        _cond.notify_all()


def status() -> dict[str, Any]:
    with _cond:
        return {
            "max_concurrent": _max_concurrent,
            "active": dict(_active_jobs),
            "active_count": len(_active_jobs),
            "pending": list(_waiting_queue),
            "pending_count": len(_waiting_queue),
            "jobs": dict(_job_status),
        }
