from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

from rich.console import Console

console = Console()

_redis_client = None
_worker_thread: threading.Thread | None = None


def _get_redis(url: str):
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(url)
    return _redis_client


def enqueue_redis(job_spec: dict[str, Any], cfg: dict[str, Any]) -> str:
    dcfg = cfg.get("distributed") or {}
    r = _get_redis(dcfg["redis_url"])
    key = dcfg.get("queue_key", "vpp:jobs")
    job_id = job_spec.get("job_name", "job")
    r.rpush(key, json.dumps(job_spec, ensure_ascii=False))
    return job_id


def start_redis_worker(handler: Callable[[dict[str, Any]], None], cfg: dict[str, Any]) -> None:
    """本机作为 Worker 消费 Redis 队列（可与 Web 同机或分离）。"""
    global _worker_thread
    dcfg = cfg.get("distributed") or {}
    if not dcfg.get("enabled") or not dcfg.get("redis_url"):
        return
    if _worker_thread and _worker_thread.is_alive():
        return
    key = dcfg.get("queue_key", "vpp:jobs")

    def _loop() -> None:
        r = _get_redis(dcfg["redis_url"])
        console.print(f"[cyan]Redis Worker[/cyan] 监听 {key}")
        while True:
            try:
                item = r.blpop(key, timeout=5)
                if not item:
                    continue
                spec = json.loads(item[1])
                handler(spec)
            except Exception as e:
                console.print(f"[yellow]Redis Worker 异常[/yellow] {e}")
                time.sleep(2)

    _worker_thread = threading.Thread(target=_loop, daemon=True, name="redis-worker")
    _worker_thread.start()
