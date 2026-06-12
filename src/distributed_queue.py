from __future__ import annotations

from typing import Any

from . import job_queue as local_queue


def is_redis_enabled(cfg: dict[str, Any]) -> bool:
    dcfg = cfg.get("distributed") or {}
    return bool(dcfg.get("redis_url")) and bool(dcfg.get("enabled", False))


def queue_status(cfg: dict[str, Any]) -> dict[str, Any]:
    """分布式队列占位：未配置 Redis 时回退本地队列。"""
    st = local_queue.status()
    st["backend"] = "redis" if is_redis_enabled(cfg) else "local"
    if is_redis_enabled(cfg):
        st["redis_note"] = "Redis 已配置；完整 Worker 分离待后续版本"
    return st
