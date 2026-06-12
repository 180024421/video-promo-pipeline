from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def save_schedule(job_dir: Path, platform: str, publish_at: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """记录定时发布元数据（需平台 API 对接时由外部 cron 读取）。"""
    entry = {
        "platform": platform,
        "publish_at": publish_at,
        "created_at": datetime.now().isoformat(),
        "status": "scheduled",
        "job_dir": str(job_dir),
    }
    path = job_dir / "publish_schedule.json"
    schedules: list[dict[str, Any]] = []
    if path.exists():
        schedules = json.loads(path.read_text(encoding="utf-8"))
    schedules.append(entry)
    path.write_text(json.dumps(schedules, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]定时发布[/green] {platform} @ {publish_at}")
    return entry


def list_pending_schedules(output_dir: Path) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    if not output_dir.exists():
        return pending
    now = datetime.now()
    for d in output_dir.iterdir():
        if not d.is_dir():
            continue
        sp = d / "publish_schedule.json"
        if not sp.exists():
            continue
        for item in json.loads(sp.read_text(encoding="utf-8")):
            if item.get("status") != "scheduled":
                continue
            try:
                when = datetime.fromisoformat(item["publish_at"])
            except Exception:
                continue
            if when <= now:
                item = dict(item)
                item["job_name"] = d.name
                item["job_dir"] = str(d)
                pending.append(item)
    return pending


def list_all_schedules(output_dir: Path) -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []
    if not output_dir.exists():
        return all_items
    for d in output_dir.iterdir():
        if not d.is_dir():
            continue
        sp = d / "publish_schedule.json"
        if not sp.exists():
            continue
        for item in json.loads(sp.read_text(encoding="utf-8")):
            if item.get("status") == "scheduled":
                row = dict(item)
                row["job_name"] = d.name
                row["job_dir"] = str(d)
                all_items.append(row)
    all_items.sort(key=lambda x: x.get("publish_at", ""))
    return all_items


def cancel_schedule(job_dir: Path, platform: str, publish_at: str) -> bool:
    path = job_dir / "publish_schedule.json"
    if not path.exists():
        return False
    items = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for item in items:
        if item.get("platform") == platform and item.get("publish_at") == publish_at and item.get("status") == "scheduled":
            item["status"] = "cancelled"
            changed = True
    if changed:
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return changed
