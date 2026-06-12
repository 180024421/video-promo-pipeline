from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import FFMPEG_INSTALL_HINT, escape_sub_path, run_ffmpeg
from .video_quality import ffmpeg_audio_args, ffmpeg_video_args

console = Console()


def resolve_ffmpeg(cfg: dict[str, Any]) -> str:
    from .ffmpeg_utils import resolve_ffmpeg as _resolve
    return _resolve(cfg)


def burn_subtitles(
    video_path: Path,
    srt_path: Path,
    cfg: dict[str, Any],
    out_dir: Path,
    *,
    fancy: bool = False,
) -> Path:
    ffmpeg = resolve_ffmpeg(cfg)
    scfg = cfg.get("subtitle", {})
    font_size = scfg.get("font_size", 22)
    margin_v = scfg.get("margin_v", 28)
    font_name = scfg.get("font_name", "Microsoft YaHei")

    if fancy:
        from .video_effects import build_fancy_ass, burn_fancy_subtitles
        ass = build_fancy_ass(srt_path, cfg, out_dir)
        out_path = out_dir / f"{video_path.stem}_subtitled{video_path.suffix}"
        return burn_fancy_subtitles(video_path, ass, cfg, out_path)

    srt_escaped = escape_sub_path(srt_path)
    style = f"FontName={font_name},FontSize={font_size},MarginV={margin_v},Outline=2,Shadow=1"
    vf = f"subtitles='{srt_escaped}':force_style='{style}'"
    out_path = out_dir / f"{video_path.stem}_subtitled{video_path.suffix}"
    vargs = ffmpeg_video_args(cfg)
    aargs = ffmpeg_audio_args(cfg, copy_audio=True)
    run_ffmpeg(
        [ffmpeg, "-y", "-i", str(video_path), "-vf", vf, *vargs, *aargs, str(out_path)],
        desc="烧录字幕",
    )
    return out_path
