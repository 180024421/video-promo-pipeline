from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def export_soft_subtitle_package(
    video_path: Path,
    srt_path: Path,
    out_dir: Path,
    cfg: dict[str, Any],
) -> Path | None:
    """软字幕包：原视频 + SRT/VTT，不烧录。"""
    pcfg = cfg.get("pipeline") or {}
    if pcfg.get("subtitle_mode", "burn") != "soft":
        return None

    soft_dir = out_dir / "soft_subtitle"
    soft_dir.mkdir(exist_ok=True)
    dest_video = soft_dir / f"{video_path.stem}_soft{video_path.suffix}"
    shutil.copy2(video_path, dest_video)

    if srt_path.exists():
        shutil.copy2(srt_path, soft_dir / srt_path.name)
    for extra in ("subtitle.vtt", "narration.srt"):
        src = out_dir / extra
        if src.exists():
            shutil.copy2(src, soft_dir / extra)

    readme = soft_dir / "README.txt"
    readme.write_text(
        "软字幕包：将同目录 .mp4 与 .srt 一并上传至 B 站等平台。\n",
        encoding="utf-8",
    )
    meta = {"video": str(dest_video), "srt": str(soft_dir / srt_path.name) if srt_path.exists() else None}
    (out_dir / "soft_subtitle.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]软字幕包[/green] {soft_dir}")
    return soft_dir
