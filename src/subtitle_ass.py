from __future__ import annotations

from pathlib import Path
from typing import Any


def _format_ass_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def segments_to_vtt(segments: list[dict[str, Any]]) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = _format_vtt_ts(seg["start"])
        end = _format_vtt_ts(seg["end"])
        text = seg.get("text", "").strip()
        if not text:
            continue
        lines.append(f"{start} --> {end}")
        lines.append(text.replace("\n", "\n"))
        lines.append("")
    return "\n".join(lines)


def _format_vtt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def segments_to_ass(segments: list[dict[str, Any]], cfg: dict[str, Any]) -> str:
    scfg = cfg.get("subtitle") or {}
    font = scfg.get("font_name", "Microsoft YaHei")
    size = int(scfg.get("font_size", 22))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,20,20,28,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    for seg in segments:
        text = seg.get("text", "").strip().replace("\n", "\\N")
        if not text:
            continue
        start = _format_ass_ts(float(seg["start"]))
        end = _format_ass_ts(float(seg["end"]))
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
    return header + "\n".join(events) + "\n"


def export_subtitle_formats(segments: list[dict[str, Any]], cfg: dict[str, Any], out_dir: Path, stem: str = "subtitle") -> dict[str, Path]:
    scfg = cfg.get("subtitle") or {}
    paths: dict[str, Path] = {}
    if scfg.get("export_vtt", True):
        p = out_dir / f"{stem}.vtt"
        p.write_text(segments_to_vtt(segments), encoding="utf-8")
        paths["vtt"] = p
    if scfg.get("export_ass", True):
        p = out_dir / f"{stem}.ass"
        p.write_text(segments_to_ass(segments, cfg), encoding="utf-8")
        paths["ass"] = p
    return paths
