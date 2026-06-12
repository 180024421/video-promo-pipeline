from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_loader import ROOT

FEEDBACK_FILE = ROOT / "data" / "ab_feedback.json"


def load_feedback() -> list[dict[str, Any]]:
    if not FEEDBACK_FILE.exists():
        return []
    return json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))


def record_feedback(entry: dict[str, Any]) -> dict[str, Any]:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    items = load_feedback()
    row = {
        "recorded_at": datetime.now().isoformat(),
        **entry,
    }
    items.append(row)
    if len(items) > 500:
        items = items[-500:]
    FEEDBACK_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return row


def suggest_from_feedback(platform: str = "bilibili") -> dict[str, Any]:
    """根据历史 CTR/播放量简单建议标题风格。"""
    items = [x for x in load_feedback() if x.get("platform", platform) == platform and x.get("views")]
    if len(items) < 2:
        return {"note": "数据不足，请录入更多 A/B 反馈"}
    best = max(items, key=lambda x: float(x.get("ctr", 0) or 0) or float(x.get("views", 0)))
    return {
        "best_title": best.get("title", ""),
        "best_ctr": best.get("ctr"),
        "best_views": best.get("views"),
        "sample_count": len(items),
    }
