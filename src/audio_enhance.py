"""音频增强：去噪、音量归一化。"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .ffmpeg_utils import resolve_ffmpeg


def apply_audio_enhance(cfg: dict[str, Any], input_video: Path, output_video: Path, *, denoise: bool = True, normalize: bool = True) -> Path | None:
    acfg = cfg.get("audio_enhance") or {}
    if not acfg.get("enabled", False):
        return None
    denoise = acfg.get("denoise", denoise)
    normalize = acfg.get("normalize", normalize)
    ffmpeg = resolve_ffmpeg(cfg)
    filters: list[str] = []
    video_cfg = cfg.get("video_quality") or {}
    preset = video_cfg.get("preset", "balanced")

    if denoise:
        filters.append("anlmdn=s=7:p=0.002:r=0.002:m=15")
    if normalize:
        filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")

    crf_map = {"fast": 23, "balanced": 18, "quality": 15}
    crf = video_cfg.get("crf") or crf_map.get(preset, 18)
    encoder = video_cfg.get("encoder", "libx264")

    cmd = [
        ffmpeg, "-i", str(input_video),
        "-c:v", encoder, "-crf", str(crf),
    ]
    if filters:
        cmd.extend(["-af", ",".join(filters)])
    cmd.extend([
        "-c:a", "aac",
        "-b:a", str(video_cfg.get("audio_bitrate", "128k")),
        str(output_video), "-y",
    ])
    output_video.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return output_video
