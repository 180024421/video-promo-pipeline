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
_cancelled: set[str] = set()
_paused = False
_priorities: dict[str, int] = {}


def configure(max_concurrent: int = 1) -> None:
    global _max_concurrent
    _max_concurrent = max(1, max_concurrent)


def set_priority(job_name: str, priority: int) -> None:
    with _cond:
        _priorities[job_name] = priority
        _resort_queue()
        _cond.notify_all()


def _resort_queue() -> None:
    if not _waiting_queue:
        return
    items = list(_waiting_queue)
    items.sort(key=lambda j: _priorities.get(j, 0), reverse=True)
    _waiting_queue.clear()
    _waiting_queue.extend(items)


def pause_queue() -> None:
    global _paused
    with _cond:
        _paused = True


def resume_queue() -> None:
    global _paused
    with _cond:
        _paused = False
        _cond.notify_all()


def cancel_job(job_name: str) -> bool:
    with _cond:
        _cancelled.add(job_name)
        new_q = deque(x for x in _waiting_queue if x != job_name)
        _waiting_queue.clear()
        _waiting_queue.extend(new_q)
        _job_status[job_name] = "cancelled"
        _cond.notify_all()
        return True


def is_cancelled(job_name: str) -> bool:
    with _lock:
        return job_name in _cancelled


def enqueue(job_name: str, priority: int = 0) -> int:
    with _cond:
        if job_name in _cancelled:
            _cancelled.discard(job_name)
        if job_name not in _waiting_queue and job_name not in _active_jobs:
            _waiting_queue.append(job_name)
            _priorities[job_name] = priority
            _resort_queue()
            _job_status[job_name] = "queued"
        try:
            return list(_waiting_queue).index(job_name) + 1
        except ValueError:
            return 0


def acquire(job_name: str, on_wait: Any = None) -> None:
    with _cond:
        if job_name not in _waiting_queue and job_name not in _active_jobs:
            _waiting_queue.append(job_name)
        while True:
            if job_name in _cancelled:
                _cancelled.discard(job_name)
                _job_status[job_name] = "cancelled"
                raise RuntimeError("任务已取消")
            if _paused:
                _job_status[job_name] = "paused"
                if on_wait:
                    try:
                        on_wait(-1)
                    except Exception:
                        pass
                _cond.wait(timeout=1.0)
                continue
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
        _priorities.pop(job_name, None)
        _cond.notify_all()


def status() -> dict[str, Any]:
    with _cond:
        return {
            "max_concurrent": _max_concurrent,
            "paused": _paused,
            "active": dict(_active_jobs),
            "active_count": len(_active_jobs),
            "pending": list(_waiting_queue),
            "pending_count": len(_waiting_queue),
            "jobs": dict(_job_status),
            "cancelled": list(_cancelled),
        }
