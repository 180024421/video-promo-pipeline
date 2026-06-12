from __future__ import annotations

from typing import Any


def _fmt_time(sec: float, fmt: str = "mm:ss") -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    if fmt == "hh:mm:ss" and sec >= 3600:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def build_chapters_from_segments(segments: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, str]]:
    if not segments:
        return []
    bcfg = (cfg.get("copy") or {}).get("bilibili") or {}
    if not bcfg.get("chapters_enabled", True):
        return []
    gen = (cfg.get("copy") or {}).get("general", {})
    max_ch = int(gen.get("max_chapters", 12))
    min_dur = float(gen.get("min_chapter_duration", 30))
    fmt = bcfg.get("timeline_format", "mm:ss")

    chapters: list[dict[str, str]] = []
    bucket_start = float(segments[0]["start"])
    bucket_text: list[str] = []

    def flush(end: float) -> None:
        nonlocal bucket_start, bucket_text
        if not bucket_text:
            return
        title = bucket_text[0][:40].strip() or "章节"
        chapters.append({"time": _fmt_time(bucket_start, fmt), "title": title})
        bucket_start = end
        bucket_text = []

    for seg in segments:
        bucket_text.append(seg.get("text", ""))
        span = float(seg["end"]) - bucket_start
        if span >= min_dur and len(chapters) < max_ch - 1:
            flush(float(seg["end"]))

    if bucket_text and len(chapters) < max_ch:
        flush(float(segments[-1]["end"]))

    return chapters[:max_ch]
