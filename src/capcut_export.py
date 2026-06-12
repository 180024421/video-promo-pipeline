from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def export_capcut_pack(job_dir: Path, cfg: dict[str, Any]) -> Path | None:
    ccfg = cfg.get("capcut") or {}
    if not ccfg.get("enabled", False):
        return None

    summary_path = job_dir / "summary.json"
    if not summary_path.exists():
        return None
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    pack_dir = job_dir / "capcut_pack"
    pack_dir.mkdir(exist_ok=True)

    video = summary.get("short_video") or summary.get("final_video")
    if video and Path(str(video)).exists():
        dest = pack_dir / Path(str(video)).name
        if not dest.exists():
            shutil.copy2(str(video), dest)

    for name in ("subtitle.srt", "narration.srt", "promo_copy.md", "xiaohongshu_post.txt"):
        src = job_dir / name
        if src.exists():
            shutil.copy2(src, pack_dir / name)

    manifest: dict[str, Any] = {
        "version": "1.0",
        "app": "CapCut/Jianying import pack",
        "video": str(pack_dir / Path(str(video)).name) if video else None,
        "subtitle": str(pack_dir / "subtitle.srt") if (pack_dir / "subtitle.srt").exists() else None,
        "import_steps": [
            "1. 打开剪映/CapCut 新建项目",
            "2. 导入 capcut_pack 目录中的 MP4",
            "3. 识别字幕或导入 SRT",
            "4. 参考 promo_copy.md 添加标题与描述",
        ],
        "segments": [],
    }
    seg_path = job_dir / "segments.json"
    if seg_path.exists():
        manifest["segments"] = json.loads(seg_path.read_text(encoding="utf-8")).get("segments", [])

    out = pack_dir / "capcut_manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]CapCut 导出包[/green] {pack_dir}")
    return pack_dir
