from __future__ import annotations

import struct
import subprocess
from pathlib import Path
from typing import Any

from .ffmpeg_utils import probe_duration, resolve_ffmpeg


def extract_waveform_peaks(
    video_path: Path,
    cfg: dict[str, Any],
    *,
    points: int = 400,
) -> dict[str, Any]:
    """用 FFmpeg 抽取单声道采样并降采样为波形峰值（供 Web 时间轴）。"""
    ffmpeg = resolve_ffmpeg(cfg)
    duration = probe_duration(cfg, video_path)
    if duration <= 0:
        return {"duration": 0, "peaks": []}

    cmd = [
        ffmpeg, "-y", "-i", str(video_path),
        "-ac", "1", "-ar", "8000", "-f", "f32le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0 or not proc.stdout:
        return {"duration": duration, "peaks": [], "error": "ffmpeg decode failed"}

    samples: list[float] = []
    for i in range(0, len(proc.stdout) - 3, 4):
        samples.append(abs(struct.unpack("<f", proc.stdout[i : i + 4])[0]))

    if not samples:
        return {"duration": duration, "peaks": []}

    bucket = max(1, len(samples) // points)
    peaks: list[float] = []
    for i in range(0, len(samples), bucket):
        chunk = samples[i : i + bucket]
        peaks.append(max(chunk) if chunk else 0.0)
    mx = max(peaks) or 1.0
    peaks = [round(p / mx, 4) for p in peaks[:points]]
    return {"duration": duration, "peaks": peaks, "points": len(peaks)}
