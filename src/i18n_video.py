from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import resolve_ffmpeg, run_ffmpeg
from .transcribe import segments_to_srt

console = Console()


def export_i18n_subtitle_track(job_dir: Path, cfg: dict[str, Any]) -> Path | None:
    """导出多语言字幕轨（软字幕 mkv 或独立 srt）。"""
    icfg = cfg.get("i18n") or {}
    if not icfg.get("enabled", False) or not icfg.get("export_video", False):
        return None

    target = icfg.get("target_language", "en")
    narr_path = job_dir / f"narration_{target}.json"
    srt_path = job_dir / f"narration_{target}.srt"
    if not srt_path.exists() and narr_path.exists():
        data = json.loads(narr_path.read_text(encoding="utf-8"))
        segs = data.get("segments", [])
        srt_path.write_text(segments_to_srt(segs), encoding="utf-8")

    if not srt_path.exists():
        console.print(f"[yellow]多语言成片[/yellow] 缺少 {srt_path.name}")
        return None

    summary_path = job_dir / "summary.json"
    video: Path | None = None
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        fv = summary.get("final_video")
        if fv:
            video = Path(str(fv))

    if not video or not video.exists():
        for p in job_dir.iterdir():
            if p.suffix.lower() == ".mp4" and "_subtitled" in p.stem:
                video = p
                break

    if not video or not video.exists():
        return srt_path

    out_path = job_dir / f"{video.stem}_{target}.mkv"
    ffmpeg = resolve_ffmpeg(cfg)
    cmd = [
        ffmpeg, "-y", "-i", str(video), "-i", str(srt_path),
        "-c", "copy", "-c:s", "srt", "-metadata:s:s:0", f"language={target}",
        str(out_path),
    ]
    run_ffmpeg(cmd, desc=f"多语言字幕轨 {target}")
    if out_path.exists():
        console.print(f"[green]多语言成片[/green] {out_path}")
        return out_path
    return srt_path
