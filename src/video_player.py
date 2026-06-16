"""视频预览播放器，支持 HLS 流和直接 MP4 播放。"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .config_loader import ROOT
from .ffmpeg_utils import resolve_ffmpeg


def generate_hls(video_path: Path, out_dir: Path, *, segment_time: int = 4) -> dict[str, Any]:
    ffmpeg = resolve_ffmpeg({})
    out_dir.mkdir(parents=True, exist_ok=True)
    playlist = out_dir / "index.m3u8"
    cmd = [
        ffmpeg, "-i", str(video_path),
        "-c:v", "libx264", "-c:a", "aac",
        "-hls_time", str(segment_time),
        "-hls_list_size", "0",
        "-hls_segment_filename", str(out_dir / "seg_%03d.ts"),
        str(playlist),
        "-y",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    segments = sorted(out_dir.glob("seg_*.ts"))
    return {"playlist": str(playlist), "segments": len(segments), "dir": str(out_dir)}


def generate_thumbnail(video_path: Path, out_path: Path, *, time_sec: float = 5.0) -> Path:
    ffmpeg = resolve_ffmpeg({})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg, "-ss", str(time_sec), "-i", str(video_path), "-vframes", "1", "-q:v", "2", str(out_path), "-y"],
        check=True, capture_output=True, text=True,
    )
    return out_path


def generate_thumbnails_sprite(video_path: Path, out_dir: Path, *, interval: int = 10, cols: int = 5) -> dict[str, Any]:
    """生成视频缩略图拼图，用于进度条预览。"""
    ffmpeg = resolve_ffmpeg({})
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "sprite.jpg"
    tile = f"{cols}x{cols}"
    cmd = [
        ffmpeg, "-i", str(video_path),
        "-vf", f"fps=1/{interval},scale=160:90,tile={tile}",
        "-frames:v", "1", "-q:v", "3", str(output), "-y",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    from .ffmpeg_utils import probe_duration

    duration = probe_duration({}, video_path)
    frame_count = int(duration / interval) + 1
    return {"sprite": str(output), "cols": cols, "frame_count": frame_count, "interval_sec": interval}
