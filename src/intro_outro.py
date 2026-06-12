from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import resolve_ffmpeg, run_ffmpeg
from .video_quality import ffmpeg_video_args

console = Console()


def apply_intro_outro(video_path: Path, cfg: dict[str, Any], out_dir: Path) -> Path:
    icfg = cfg.get("intro_outro") or {}
    if not icfg.get("enabled", False):
        return video_path

    intro = icfg.get("intro", "")
    outro = icfg.get("outro", "")
    intro_p = Path(intro) if intro else None
    outro_p = Path(outro) if outro else None
    if intro_p and not intro_p.exists():
        intro_p = None
    if outro_p and not outro_p.exists():
        outro_p = None
    if not intro_p and not outro_p:
        return video_path

    ffmpeg = resolve_ffmpeg(cfg)
    parts = []
    list_lines: list[str] = []
    idx = 0
    for p in (intro_p, video_path, outro_p):
        if p and p.exists():
            parts.extend(["-i", str(p)])
            list_lines.append(f"file '{p.resolve().as_posix()}'")
            idx += 1

    if len(parts) <= 2:
        return video_path

    out_path = out_dir / f"{video_path.stem}_branded{video_path.suffix}"
    list_file = out_dir / "concat_brand.txt"
    list_file.write_text("\n".join(list_lines), encoding="utf-8")
    vargs = ffmpeg_video_args(cfg)
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), *vargs, "-c:a", "aac", "-b:a", "128k", str(out_path)]
    run_ffmpeg(cmd, desc="片头片尾拼接")
    return out_path if out_path.exists() else video_path
