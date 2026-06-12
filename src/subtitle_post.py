from __future__ import annotations

import re
from typing import Any

FILLERS = ("嗯", "啊", "呃", "那个", "就是")


def _wrap_line(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    parts: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= max_chars and ch in "，。！？、 ":
            parts.append(buf.strip())
            buf = ""
    if buf.strip():
        parts.append(buf.strip())
    return "\n".join(parts) if parts else text


def post_process_segments(segments: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    scfg = cfg.get("subtitle") or {}
    max_chars = int(scfg.get("max_chars_per_line", 18))
    merge_min = float(scfg.get("merge_min_duration", 1.2))
    remove_fillers = scfg.get("remove_fillers", True)

    cleaned: list[dict[str, Any]] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if remove_fillers and text in FILLERS:
            continue
        if remove_fillers:
            for f in FILLERS:
                if text == f or text.startswith(f + "，"):
                    text = text[len(f):].lstrip("，")
        if not text:
            continue
        text = _wrap_line(text, max_chars)
        cleaned.append({**seg, "text": text})

    if not cleaned:
        return segments

    merged: list[dict[str, Any]] = [cleaned[0]]
    for seg in cleaned[1:]:
        prev = merged[-1]
        dur = float(seg["end"]) - float(seg["start"])
        if dur < merge_min and len(prev.get("text", "")) < max_chars * 2:
            prev["end"] = seg["end"]
            prev["text"] = prev["text"].rstrip() + seg["text"]
        else:
            merged.append(seg)
    return merged
