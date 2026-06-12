from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from .subtitle_ass import export_subtitle_formats
from .subtitle_post import post_process_segments
from .terminology import apply_replacements, apply_to_segments, load_terminology

console = Console()


def _format_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        start = _format_ts(seg["start"])
        end = _format_ts(seg["end"])
        text = seg["text"].strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def build_chapter_outline(segments: list[dict[str, Any]], max_items: int = 12) -> str:
    if not segments:
        return ""
    step = max(1, len(segments) // max_items)
    lines: list[str] = []
    for seg in segments[::step][:max_items]:
        m = int(seg["start"] // 60)
        s = int(seg["start"] % 60)
        lines.append(f"{m:02d}:{s:02d} {seg.get('text', '')[:40]}")
    return "\n".join(lines)


def transcribe_video(video_path: Path, cfg: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    from faster_whisper import WhisperModel

    wcfg = cfg.get("whisper", {})
    model_size = wcfg.get("model", "medium")
    device = wcfg.get("device", "cuda")
    compute_type = wcfg.get("compute_type", "float16")
    language = wcfg.get("language", "zh")

    console.print(f"[cyan]Whisper 转写[/cyan] model={model_size} device={device}")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments_iter, info = model.transcribe(
        str(video_path),
        language=language,
        vad_filter=True,
        beam_size=5,
    )

    segments: list[dict[str, Any]] = []
    for seg in segments_iter:
        segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        })

    replacements = load_terminology(cfg)
    segments = apply_to_segments(segments, replacements)
    segments = post_process_segments(segments, cfg)

    transcript = "\n".join(s["text"] for s in segments if s["text"])
    transcript = apply_replacements(transcript, replacements)
    srt_text = segments_to_srt(segments)

    srt_path = out_dir / "subtitle.srt"
    txt_path = out_dir / "transcript.txt"
    json_path = out_dir / "segments.json"

    srt_path.write_text(srt_text, encoding="utf-8")
    txt_path.write_text(transcript, encoding="utf-8")
    json_path.write_text(
        json.dumps({"language": info.language, "duration": info.duration, "segments": segments}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    extra = export_subtitle_formats(segments, cfg, out_dir)

    console.print(f"[green]字幕已生成[/green] {srt_path}")
    return {
        "srt_path": srt_path,
        "transcript_path": txt_path,
        "segments_path": json_path,
        "transcript": transcript,
        "segments": segments,
        "chapter_outline": build_chapter_outline(segments),
        "duration": info.duration,
        "subtitle_formats": {k: str(v) for k, v in extra.items()},
    }
