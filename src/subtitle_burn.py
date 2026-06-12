from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def resolve_ffmpeg(cfg: dict[str, Any]) -> str:
    custom = cfg.get("ffmpeg", {}).get("path") or ""
    if custom:
        return custom
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("未找到 ffmpeg，请安装并加入 PATH: https://ffmpeg.org/download.html")
    return found


def burn_subtitles(video_path: Path, srt_path: Path, cfg: dict[str, Any], out_dir: Path) -> Path:
    ffmpeg = resolve_ffmpeg(cfg)
    scfg = cfg.get("subtitle", {})
    font_size = scfg.get("font_size", 22)
    margin_v = scfg.get("margin_v", 28)
    font_name = scfg.get("font_name", "Microsoft YaHei")

    srt_escaped = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
    style = f"FontName={font_name},FontSize={font_size},MarginV={margin_v},Outline=2,Shadow=1"
    vf = f"subtitles='{srt_escaped}':force_style='{style}'"

    out_path = out_dir / f"{video_path.stem}_subtitled{video_path.suffix}"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        vf,
        "-c:a",
        "copy",
        str(out_path),
    ]

    console.print("[cyan]FFmpeg 烧录字幕[/cyan]")
    subprocess.run(cmd, check=True)
    console.print(f"[green]成片已生成[/green] {out_path}")
    return out_path
