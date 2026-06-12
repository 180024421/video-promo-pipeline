from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import resolve_ffmpeg

console = Console()


def _run_ffmpeg_stats(cfg: dict[str, Any], video_path: Path, filters: str) -> str:
    ffmpeg = resolve_ffmpeg(cfg)
    cmd = [
        ffmpeg, "-hide_banner", "-i", str(video_path),
        "-af", filters, "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.stderr or ""


def analyze_video(video_path: Path, cfg: dict[str, Any], out_dir: Path | None = None) -> dict[str, Any]:
    """成片质检：音量、静音段、黑场。"""
    qcfg = cfg.get("video_qc") or {}
    if not qcfg.get("enabled", True):
        return {"skipped": True}

    report: dict[str, Any] = {"video": str(video_path), "issues": [], "warnings": []}

    vol_log = _run_ffmpeg_stats(cfg, video_path, "volumedetect")
    m = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", vol_log)
    if m:
        mean_db = float(m.group(1))
        report["mean_volume_db"] = mean_db
        min_db = float(qcfg.get("min_mean_volume_db", -35))
        max_db = float(qcfg.get("max_mean_volume_db", -5))
        if mean_db < min_db:
            report["issues"].append(f"音量过低 ({mean_db:.1f} dB)")
        elif mean_db > max_db:
            report["warnings"].append(f"音量偏高 ({mean_db:.1f} dB)")

    silence_log = _run_ffmpeg_stats(
        cfg, video_path,
        f"silencedetect=noise={qcfg.get('silence_noise_db', -40)}dB:d={qcfg.get('max_silence_sec', 3)}",
    )
    silence_count = len(re.findall(r"silence_start", silence_log))
    report["long_silence_segments"] = silence_count
    if silence_count > int(qcfg.get("max_silence_segments", 5)):
        report["warnings"].append(f"过长静音段 {silence_count} 处")

    black_log = _run_ffmpeg_stats(
        cfg, video_path,
        f"blackdetect=d={qcfg.get('black_min_duration', 0.5)}:pix_th={qcfg.get('black_pixel_ratio', 0.1)}",
    )
    black_count = len(re.findall(r"black_start", black_log))
    report["black_segments"] = black_count
    if black_count > int(qcfg.get("max_black_segments", 3)):
        report["warnings"].append(f"黑场片段 {black_count} 处")

    report["ok"] = len(report["issues"]) == 0
    if out_dir:
        path = out_dir / "qc_report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]质检报告[/green] {path}")
    return report
