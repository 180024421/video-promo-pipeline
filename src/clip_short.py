from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

from .face_crop import build_vertical_crop_filter
from .ffmpeg_utils import probe_duration, resolve_ffmpeg, run_ffmpeg
from .smart_select import pick_highlight_window, pick_multiple_highlight_windows
from .video_quality import ffmpeg_audio_args, ffmpeg_video_args
from .video_effects import (
    build_fancy_ass,
    build_watermark_filter,
    burn_fancy_subtitles,
    mix_bgm_on_video,
)

console = Console()

StepCallback = Callable[[str], None] | None


def _pick_start_legacy(segments: list[dict[str, Any]], duration: float, position: str) -> float:
    if not segments:
        return 0.0
    if position == "middle":
        return max(0.0, duration / 2 - 37.5)
    if position == "end":
        return max(0.0, duration - 75)
    if position == "chapter_first" and len(segments) > 1:
        return float(segments[1].get("start", 0))
    if position == "random":
        import random
        return random.uniform(0, max(0, duration - 30))
    return 0.0


def _render_one_clip(
    ffmpeg: str,
    video_path: Path,
    out_dir: Path,
    cfg: dict[str, Any],
    *,
    start: float,
    actual_len: float,
    width: int,
    height: int,
    suffix: str,
    subtitle_srt: Path | None,
) -> Path:
    tmp_clip = out_dir / f"{video_path.stem}_short_raw{suffix}.mp4"
    wm = build_watermark_filter(cfg)
    vf_crop = build_vertical_crop_filter(cfg, video_path, ffmpeg, start, out_dir)
    vf_parts = [vf_crop, f"scale={width}:{height}"]
    if wm:
        vf_parts.append(wm)
    vf = ",".join(vf_parts)
    vargs = ffmpeg_video_args(cfg)
    aargs = ffmpeg_audio_args(cfg)
    cmd = [
        ffmpeg, "-y", "-ss", str(start), "-i", str(video_path),
        "-t", str(actual_len), "-vf", vf,
        *vargs, *aargs, str(tmp_clip),
    ]
    run_ffmpeg(cmd, desc=f"竖屏切片 {actual_len:.0f}s from {start:.1f}s")

    work = tmp_clip
    bgm_out = out_dir / f"{video_path.stem}_short_bgm{suffix}.mp4"
    mixed = mix_bgm_on_video(work, cfg, bgm_out, segments=None)
    if mixed != work:
        work = mixed

    out_path = out_dir / f"{video_path.stem}_short_{height}p{suffix}.mp4"
    ccfg = cfg.get("clip_short") or {}
    cstyle = ccfg.get("caption_style") or {}
    if cstyle.get("enabled", False) and subtitle_srt and subtitle_srt.exists():
        ass = build_fancy_ass(subtitle_srt, cfg, out_dir)
        burn_fancy_subtitles(work, ass, cfg, out_path)
    else:
        import shutil
        shutil.copy2(work, out_path)
    return out_path


def clip_vertical_short(
    video_path: Path,
    segments: list[dict[str, Any]],
    cfg: dict[str, Any],
    out_dir: Path,
    *,
    transcript: str = "",
    subtitle_srt: Path | None = None,
    on_step: StepCallback = None,
) -> Path | None:
    ccfg = cfg.get("clip_short") or {}
    if not ccfg.get("enabled", True):
        return None

    if on_step:
        on_step("竖屏切片")

    ffmpeg = resolve_ffmpeg(cfg)
    clip_len = int(ccfg.get("duration_sec", 75))
    width = int(ccfg.get("width", 1080))
    height = int(ccfg.get("height", 1920))
    position = ccfg.get("position", "start")
    duration = probe_duration(cfg, video_path)
    multi_count = int(ccfg.get("multi_clip_count", 1))
    windows: list[tuple[float, float]] = []

    if position == "smart" or (ccfg.get("smart_select") or {}).get("enabled", False):
        if multi_count > 1:
            windows = pick_multiple_highlight_windows(
                transcript or "", segments, cfg,
                clip_len=clip_len, video_duration=duration, count=multi_count,
            )
        else:
            start, actual_len = pick_highlight_window(
                transcript or "", segments, cfg, clip_len=clip_len, video_duration=duration,
            )
            windows = [(start, actual_len)]
    else:
        beat_windows = None
        try:
            from .bgm_beat import suggest_clip_windows_by_beat
            beat_windows = suggest_clip_windows_by_beat(duration, cfg, clip_len)
        except Exception:
            pass
        if beat_windows and (cfg.get("bgm_beat") or {}).get("enabled", False):
            windows = beat_windows
        else:
            start = _pick_start_legacy(segments, duration, position)
            actual_len = float(clip_len)
            if start + actual_len > duration:
                start = max(0.0, duration - actual_len)
            windows = [(start, actual_len)]

    outputs: list[dict[str, Any]] = []
    for idx, (start, actual_len) in enumerate(windows):
        if start + actual_len > duration:
            start = max(0.0, duration - actual_len)
        suffix = f"_{idx + 1}" if len(windows) > 1 else ""
        out_path = _render_one_clip(
            ffmpeg, video_path, out_dir, cfg,
            start=start, actual_len=actual_len, width=width, height=height,
            suffix=suffix, subtitle_srt=subtitle_srt,
        )
        outputs.append({"index": idx + 1, "start": start, "duration": actual_len, "output": str(out_path)})

    meta = {"clips": outputs, "primary": outputs[0] if outputs else None}
    (out_dir / "clip_short.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    primary = Path(outputs[0]["output"]) if outputs else None
    if primary:
        console.print(f"[green]竖屏成片[/green] {len(outputs)} 个 → {primary}")
    return primary
