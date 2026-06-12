from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def run_auto_editor(video_path: Path, cfg: dict[str, Any], out_dir: Path) -> Path | None:
    acfg = cfg.get("auto_editor", {})
    if not acfg.get("enabled", True):
        console.print("[yellow]已跳过 Auto-Editor 粗剪[/yellow]")
        return None

    if shutil.which("auto-editor") is None:
        console.print("[yellow]未找到 auto-editor，跳过粗剪[/yellow]")
        return None

    threshold = acfg.get("silent_threshold", 0.04)
    min_silence = acfg.get("min_silence_duration", 0.35)
    out_path = out_dir / f"{video_path.stem}_cut{video_path.suffix}"

    cmd = [
        "auto-editor",
        str(video_path),
        "--edit",
        "audio",
        "--frame_rate",
        "30",
        "--output",
        str(out_path),
        "--silent_threshold",
        str(threshold),
        "--min_clip_duration",
        str(min_silence),
    ]

    console.print(f"[cyan]Auto-Editor 粗剪[/cyan] threshold={threshold} min_clip={min_silence}")
    subprocess.run(cmd, check=True)
    if acfg.get("reencode_quality", False) and out_path.exists():
        from .ffmpeg_utils import resolve_ffmpeg, run_ffmpeg
        from .video_quality import ffmpeg_audio_args, ffmpeg_video_args
        ffmpeg = resolve_ffmpeg(cfg)
        tmp = out_dir / f"{video_path.stem}_cut_re{video_path.suffix}"
        vargs = ffmpeg_video_args(cfg)
        aargs = ffmpeg_audio_args(cfg, copy_audio=True)
        run_ffmpeg([ffmpeg, "-y", "-i", str(out_path), *vargs, *aargs, str(tmp)], desc="粗剪质量重编码")
        if tmp.exists():
            out_path = tmp
    console.print(f"[green]粗剪完成[/green] {out_path}")
    return out_path
