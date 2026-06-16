"""场景检测：转场、PPT 翻页、代码切换。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ffmpeg_utils import resolve_ffmpeg


def detect_scene_changes(cfg: dict[str, Any], video_path: Path, *, threshold: float = 0.3) -> list[dict[str, Any]]:
    """使用 FFmpeg scene detect 检测转场时间点。"""
    import subprocess

    ffmpeg = resolve_ffmpeg(cfg)
    proc = subprocess.run(
        [
            ffmpeg, "-i", str(video_path),
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, check=False,
    )
    scenes: list[dict[str, Any]] = []
    for line in (proc.stderr or "").splitlines():
        if "pts_time:" in line:
            import re

            m = re.search(r"pts_time:([\d.]+)", line)
            if m:
                scenes.append({"time_sec": round(float(m.group(1)), 2), "type": "scene_change"})
    return scenes


def export_scenes_json(video_path: Path, out_dir: Path, cfg: dict[str, Any] | None = None, *, threshold: float = 0.3) -> Path:
    scenes = detect_scene_changes(cfg or {}, video_path, threshold=threshold)
    out_path = out_dir / "scenes.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
