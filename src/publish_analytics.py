"""发布分析：播放数据追踪面板。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_loader import ROOT


def record_analytics(job_name: str, platform: str, **stats: Any) -> dict[str, Any]:
    entry = {
        "job": job_name,
        "platform": platform,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats,
    }
    path = ROOT / "data" / "publish_analytics.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load_analytics(limit: int = 50) -> list[dict[str, Any]]:
    path = ROOT / "data" / "publish_analytics.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows[-limit:]


def analytics_summary() -> dict[str, Any]:
    rows = load_analytics(200)
    total_views = sum(r.get("views", 0) for r in rows)
    total_likes = sum(r.get("likes", 0) for r in rows)
    by_platform: dict[str, int] = {}
    for r in rows:
        p = r.get("platform", "unknown")
        by_platform[p] = by_platform.get(p, 0) + r.get("views", 0)
    return {
        "total_views": total_views,
        "total_likes": total_likes,
        "by_platform": by_platform,
        "recent": rows[-10:],
    }
