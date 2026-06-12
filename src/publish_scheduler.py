from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from .config_loader import load_config

console = Console()

_scheduler_thread: threading.Thread | None = None
_stop = threading.Event()


def execute_schedule(entry: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    platform = entry.get("platform", "bilibili")
    job_dir = Path(entry.get("job_dir", ""))
    publish_at = entry.get("publish_at", "")
    if not job_dir.is_dir():
        return {"ok": False, "error": "任务目录不存在"}
    if platform == "bilibili":
        from .publish import publish_bilibili

        try:
            result = publish_bilibili(job_dir, cfg)
            ok = not result.get("error") and not result.get("skipped")
            _mark_done(job_dir, platform, publish_at, "done" if ok else "failed", json.dumps(result, ensure_ascii=False)[:500])
            return {"ok": ok, "result": result}
        except Exception as e:
            _mark_done(job_dir, platform, publish_at, "failed", str(e))
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": f"平台 {platform} 暂不支持自动定时发布"}


def _mark_done(job_dir: Path, platform: str, publish_at: str, status: str, detail: str = "") -> None:
    path = job_dir / "publish_schedule.json"
    if not path.exists():
        return
    items = json.loads(path.read_text(encoding="utf-8"))
    for item in items:
        if item.get("platform") == platform and item.get("publish_at") == publish_at:
            item["status"] = status
            item["executed_at"] = datetime.now().isoformat()
            if detail:
                item["detail"] = detail
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def run_due_schedules(output_dir: Path, cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    from .publish_schedule import list_pending_schedules

    cfg = cfg or load_config()
    due = list_pending_schedules(output_dir)
    results: list[dict[str, Any]] = []
    for entry in due:
        console.print(f"[cyan]定时发布[/cyan] {entry.get('job_name')} → {entry.get('platform')}")
        r = execute_schedule(entry, cfg)
        results.append({"entry": entry, **r})
    return results


def _scheduler_loop(output_dir: Path, interval_sec: int) -> None:
    while not _stop.is_set():
        try:
            run_due_schedules(output_dir)
        except Exception as e:
            console.print(f"[yellow]定时发布调度异常[/yellow] {e}")
        _stop.wait(interval_sec)


def start_scheduler(output_dir: Path, interval_sec: int = 60) -> None:
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(output_dir, interval_sec),
        daemon=True,
        name="publish-scheduler",
    )
    _scheduler_thread.start()


def stop_scheduler() -> None:
    _stop.set()
