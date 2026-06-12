from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def build_youtube_manifest(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """YouTube 发布清单 + 章节描述（API 上传需 OAuth，此处生成 manifest）。"""
    pcfg = (cfg.get("publish") or {}).get("youtube") or {}
    if not pcfg.get("enabled", False):
        return {"skipped": True}

    summary = {}
    if (job_dir / "summary.json").exists():
        summary = json.loads((job_dir / "summary.json").read_text(encoding="utf-8"))
    promo = {}
    if (job_dir / "promo_copy.json").exists():
        promo = json.loads((job_dir / "promo_copy.json").read_text(encoding="utf-8"))

    chapters = ""
    ch_path = job_dir / "chapters_youtube.txt"
    if ch_path.exists():
        chapters = ch_path.read_text(encoding="utf-8")

    yt = promo.get("youtube") or promo.get("bilibili") or {}
    title = yt.get("recommended_title") or yt.get("title") or job_dir.name.split("_")[0]
    desc = yt.get("description", "")
    if chapters:
        desc = f"{desc}\n\n{chapters}".strip()

    manifest = {
        "platform": "youtube",
        "video": summary.get("final_video"),
        "title": title[:100],
        "description": desc[:5000],
        "tags": yt.get("tags", []),
        "category_id": pcfg.get("category_id", "28"),
        "privacy": pcfg.get("privacy", "private"),
        "manual_steps": [
            "1. YouTube Studio → 创建 → 上传视频",
            "2. 粘贴 title / description（含章节时间戳）",
            "3. 配置 OAuth 后可对接 Data API v3 自动上传",
        ],
        "upload_url": "https://studio.youtube.com/",
    }
    out = job_dir / "publish_youtube.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]YouTube 清单[/green] {out}")
    return manifest
