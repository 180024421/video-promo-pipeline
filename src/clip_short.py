from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from .subtitle_burn import resolve_ffmpeg

console = Console()


def _pick_start(segments: list[dict[str, Any]], duration: float, position: str) -> float:
    if not segments:
        return 0.0
    if position == "middle":
        return max(0.0, duration / 2 - 37.5)
    if position == "chapter_first" and len(segments) > 1:
        return float(segments[1].get("start", 0))
    return 0.0


def clip_vertical_short(
    video_path: Path,
    segments: list[dict[str, Any]],
    cfg: dict[str, Any],
    out_dir: Path,
) -> Path | None:
    ccfg = cfg.get("clip_short") or {}
    if not ccfg.get("enabled", True):
        return None

    ffmpeg = resolve_ffmpeg(cfg)
    clip_len = int(ccfg.get("duration_sec", 75))
    width = int(ccfg.get("width", 1080))
    height = int(ccfg.get("height", 1920))
    position = ccfg.get("position", "start")

    dur_probe = subprocess.run(
        [ffmpeg, "-i", str(video_path)],
        capture_output=True,
        text=True,
    )
    # crude duration from stderr; fallback 300s
    duration = 300.0
    for line in dur_probe.stderr.splitlines():
        if "Duration:" in line:
            try:
                t = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = t.split(":")
                duration = int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                pass
            break

    start = _pick_start(segments, duration, position)
    if start + clip_len > duration:
        start = max(0.0, duration - clip_len)

    out_path = out_dir / f"{video_path.stem}_short_{height}p.mp4"
    # crop center for 16:9 -> 9:16
    vf = (
        f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,"
        f"scale={width}:{height}"
    )
    cmd = [
        ffmpeg, "-y",
        "-ss", str(start),
        "-i", str(video_path),
        "-t", str(clip_len),
        "-vf", vf,
        "-c:a", "aac",
        "-b:a", "128k",
        str(out_path),
    ]
    console.print(f"[cyan]竖屏切片[/cyan] {clip_len}s from {start:.1f}s")
    subprocess.run(cmd, check=True)
    meta = {"start": start, "duration": clip_len, "output": str(out_path)}
    (out_dir / "clip_short.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    console.print(f"[green]小红书竖屏片段[/green] {out_path}")
    return out_path
