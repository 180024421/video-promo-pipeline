from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def build_publish_pack(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """生成一键复制/上架素材包说明。"""
    summary_path = job_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    promo = {}
    if (job_dir / "promo_copy.json").exists():
        promo = json.loads((job_dir / "promo_copy.json").read_text(encoding="utf-8"))

    pack: dict[str, Any] = {
        "job": job_dir.name,
        "video": summary.get("final_video") or summary.get("short_video"),
        "short_clips": [],
        "clipboard": {},
    }
    clip_meta = job_dir / "clip_short.json"
    if clip_meta.exists():
        cm = json.loads(clip_meta.read_text(encoding="utf-8"))
        if cm.get("clips"):
            pack["short_clips"] = [c.get("output") for c in cm["clips"]]
        elif cm.get("output"):
            pack["short_clips"] = [cm["output"]]

    b = promo.get("bilibili") or {}
    if b:
        pack["clipboard"]["bilibili_title"] = (b.get("recommended_title") or (b.get("titles") or [""])[0])
        pack["clipboard"]["bilibili_description"] = b.get("description", "")
        if (job_dir / "bilibili_description.txt").exists():
            pack["clipboard"]["bilibili_description"] = (job_dir / "bilibili_description.txt").read_text(encoding="utf-8")
        ch_lines = []
        for ch in b.get("chapters") or []:
            ch_lines.append(f"{ch.get('time', '')} {ch.get('title', '')}")
        if ch_lines:
            pack["clipboard"]["bilibili_chapters"] = "\n".join(ch_lines)

    x = promo.get("xiaohongshu") or {}
    if x:
        pack["clipboard"]["xiaohongshu"] = f"{x.get('title', '')}\n\n{x.get('body', '')}\n\n{' '.join(x.get('topics', []))}"

    d = promo.get("douyin") or {}
    if d:
        pack["clipboard"]["douyin"] = f"{d.get('title', '')}\n\n{d.get('body', '')}"

    out = job_dir / "publish_pack.json"
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]发布素材包[/green] {out}")
    return pack


def save_segments_and_srt(job_dir: Path, segments: list[dict[str, Any]], cfg: dict[str, Any]) -> None:
    from .transcribe import build_chapter_outline, segments_to_srt
    from .subtitle_ass import export_subtitle_formats
    from .terminology import apply_to_segments, load_terminology

    replacements = load_terminology(cfg)
    segments = apply_to_segments(segments, replacements)
    srt = segments_to_srt(segments)
    (job_dir / "subtitle.srt").write_text(srt, encoding="utf-8")
    (job_dir / "transcript.txt").write_text("\n".join(s["text"] for s in segments if s.get("text")), encoding="utf-8")
    (job_dir / "segments.json").write_text(
        json.dumps({"segments": segments, "chapter_outline": build_chapter_outline(segments)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    export_subtitle_formats(segments, cfg, job_dir)
