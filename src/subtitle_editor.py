"""字幕时间轴编辑器：基于 waveform 的拖拽编辑。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_subtitle_segments(segments_path: Path) -> list[dict[str, Any]]:
    """从 segments.json 加载字幕段。"""
    data = json.loads(segments_path.read_text(encoding="utf-8")) if segments_path.exists() else []
    return data if isinstance(data, list) else data.get("segments", [])


def save_subtitle_segments(segments_path: Path, segments: list[dict[str, Any]]) -> Path:
    segments_path.parent.mkdir(parents=True, exist_ok=True)
    segments_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    return segments_path


def merge_segments(i: int, j: int, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并两个相邻片段。"""
    if not (0 <= i < len(segments) and 0 <= j < len(segments)):
        return segments
    if i > j:
        i, j = j, i
    a, b = segments[i], segments[j]
    merged = {
        "start": min(a["start"], b["start"]),
        "end": max(a["end"], b["end"]),
        "text": str(a.get("text", "")) + " " + str(b.get("text", "")),
    }
    out = segments[:i] + [merged] + segments[j + 1:]
    return out


def split_segment(i: int, at_sec: float, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """在指定时间点拆分片段。"""
    if not (0 <= i < len(segments)):
        return segments
    s = segments[i]
    if at_sec <= s["start"] or at_sec >= s["end"]:
        return segments
    text = str(s.get("text", ""))
    ratio = (at_sec - s["start"]) / max(s["end"] - s["start"], 0.01)
    split_point = max(1, int(len(text) * ratio))
    first = {"start": s["start"], "end": at_sec, "text": text[:split_point].strip()}
    second = {"start": at_sec, "end": s["end"], "text": text[split_point:].strip()}
    return segments[:i] + [first, second] + segments[i + 1:]


def update_segment_time(i: int, start: float | None, end: float | None, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """更新片段起止时间。"""
    if not (0 <= i < len(segments)):
        return segments
    s = dict(segments[i])
    if start is not None:
        s["start"] = start
    if end is not None:
        s["end"] = end
    out = list(segments)
    out[i] = s
    return out


def update_segment_text(i: int, text: str, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not (0 <= i < len(segments)):
        return segments
    s = dict(segments[i])
    s["text"] = text
    out = list(segments)
    out[i] = s
    return out


def delete_segment(i: int, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not (0 <= i < len(segments)):
        return segments
    return segments[:i] + segments[i + 1:]
