from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from .cover import generate_cover
from .ffmpeg_utils import probe_duration, resolve_ffmpeg

console = Console()


def select_best_cover(
    title: str,
    cfg: dict[str, Any],
    out_dir: Path,
    source_video: Path,
    copy_data: dict[str, Any] | None = None,
) -> Path | None:
    ccfg = cfg.get("cover") or {}
    if not ccfg.get("ai_frame_select", False) or not source_video.exists():
        return generate_cover(title, cfg, out_dir, copy_data, source_video=source_video)

    ffmpeg = resolve_ffmpeg(cfg)
    dur = probe_duration(cfg, source_video)
    ratios = [0.1, 0.25, 0.4, 0.55, 0.7]
    frames: list[Path] = []
    scores: list[dict[str, Any]] = []

    for i, r in enumerate(ratios):
        ts = dur * r
        fp = out_dir / f"_frame_candidate_{i}.jpg"
        subprocess.run(
            [ffmpeg, "-y", "-ss", str(ts), "-i", str(source_video), "-vframes", "1", "-q:v", "2", str(fp)],
            check=False,
            capture_output=True,
        )
        if fp.exists():
            frames.append(fp)
            score = _score_frame(fp, cfg, copy_data)
            scores.append({"index": i, "time": ts, "score": score, "path": str(fp)})

    if not scores:
        return generate_cover(title, cfg, out_dir, copy_data, source_video=source_video)

    best = max(scores, key=lambda x: x["score"])
    ccfg_override = {**cfg, "cover": {**ccfg, "frame_position_ratio": best["time"] / max(dur, 1)}}
    (out_dir / "cover_frame_scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]封面选帧[/green] t={best['time']:.1f}s score={best['score']}")
    return generate_cover(title, ccfg_override, out_dir, copy_data, source_video=source_video)


def _score_frame(frame: Path, cfg: dict[str, Any], copy_data: dict[str, Any] | None) -> float:
    try:
        from PIL import Image, ImageStat

        img = Image.open(frame).convert("L")
        stat = ImageStat.Stat(img)
        contrast = stat.stddev[0]
        brightness = stat.mean[0]
        score = float(contrast) - abs(brightness - 128) * 0.3
        if copy_data:
            kw = (copy_data.get("bilibili") or {}).get("keywords") or []
            score += min(len(kw), 5) * 0.5
        return round(score, 2)
    except Exception:
        return 0.0
