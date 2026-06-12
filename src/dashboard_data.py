from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .publish_schedule import list_all_schedules


def build_dashboard(output_dir: Path) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    if not output_dir.exists():
        return {"jobs": [], "schedules": [], "stats": {}}

    for d in sorted(output_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        row: dict[str, Any] = {"name": d.name, "status": "unknown", "links": {}}
        sp = d / "summary.json"
        if sp.exists():
            s = json.loads(sp.read_text(encoding="utf-8"))
            row["final_video"] = s.get("final_video")
            row["cover"] = s.get("cover")
        prog = d / "pipeline_progress.json"
        if prog.exists():
            p = json.loads(prog.read_text(encoding="utf-8"))
            row["status"] = "done" if p.get("current") == "完成" else ("error" if p.get("error") else "running")
        for pub_file, key in (
            ("publish_bilibili.json", "bilibili"),
            ("publish_youtube.json", "youtube"),
            ("publish_douyin.json", "douyin"),
        ):
            pf = d / pub_file
            if pf.exists():
                pub = json.loads(pf.read_text(encoding="utf-8"))
                bvid = pub.get("bvid") or pub.get("aid")
                if bvid:
                    row["links"][key] = f"https://www.bilibili.com/video/{bvid}" if key == "bilibili" else pub.get("upload_url", "")
                else:
                    row["links"][key] = pub.get("upload_url", "")
        jobs.append(row)

    schedules = list_all_schedules(output_dir)
    done = sum(1 for j in jobs if j["status"] == "done")
    return {
        "jobs": jobs[:80],
        "schedules": schedules,
        "stats": {"total": len(jobs), "done": done, "scheduled": len(schedules)},
    }
