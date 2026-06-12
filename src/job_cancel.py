from __future__ import annotations

import threading

_lock = threading.Lock()
_cancelled: set[str] = set()


def request_cancel(job_name: str) -> None:
    with _lock:
        _cancelled.add(job_name)


def clear_cancel(job_name: str) -> None:
    with _lock:
        _cancelled.discard(job_name)


def is_cancel_requested(job_name: str) -> bool:
    with _lock:
        return job_name in _cancelled


def check_cancel(job_name: str) -> None:
    if is_cancel_requested(job_name):
        raise RuntimeError("任务已取消")
