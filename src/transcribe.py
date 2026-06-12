from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import probe_duration, resolve_ffmpeg
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


def _split_video_chunks(video_path: Path, cfg: dict[str, Any], chunk_sec: float, tmp_dir: Path) -> list[tuple[Path, float]]:
    ffmpeg = resolve_ffmpeg(cfg)
    duration = probe_duration(cfg, video_path)
    if duration <= chunk_sec:
        return [(video_path, 0.0)]

    chunks: list[tuple[Path, float]] = []
    start = 0.0
    idx = 0
    while start < duration - 0.5:
        end = min(start + chunk_sec, duration)
        out = tmp_dir / f"chunk_{idx:03d}.wav"
        subprocess.run(
            [
                ffmpeg, "-y", "-ss", str(start), "-i", str(video_path),
                "-t", str(end - start), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(out),
            ],
            check=True,
            capture_output=True,
        )
        chunks.append((out, start))
        start = end
        idx += 1
    console.print(f"[cyan]长视频分块[/cyan] {len(chunks)} 段 × ~{chunk_sec / 60:.0f} 分钟")
    return chunks


def _transcribe_whisper(model: Any, audio_path: Path, cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], Any]:
    wcfg = cfg.get("whisper", {})
    language = wcfg.get("language", "zh")
    beam_size = int(wcfg.get("beam_size", 5))
    vad_filter = bool(wcfg.get("vad_filter", True))
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=vad_filter,
        beam_size=beam_size,
    )
    segments: list[dict[str, Any]] = []
    for seg in segments_iter:
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
    return segments, info


def transcribe_video(video_path: Path, cfg: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    from faster_whisper import WhisperModel

    wcfg = cfg.get("whisper", {})
    model_size = wcfg.get("model", "medium")
    device = wcfg.get("device", "cuda")
    compute_type = wcfg.get("compute_type", "float16")
    chunk_if_longer = float(wcfg.get("chunk_if_longer_sec", 1800))
    chunk_minutes = float(wcfg.get("chunk_minutes", 15))
    chunk_sec = chunk_minutes * 60

    console.print(f"[cyan]Whisper 转写[/cyan] model={model_size} device={device}")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    duration = probe_duration(cfg, video_path)
    use_chunks = duration > chunk_if_longer and chunk_sec > 0
    segments: list[dict[str, Any]] = []
    info: Any = None

    if use_chunks:
        tmp_dir = Path(tempfile.mkdtemp(prefix="whisper_chunks_"))
        try:
            chunks = _split_video_chunks(video_path, cfg, chunk_sec, tmp_dir)
            for idx, (chunk_path, offset) in enumerate(chunks, 1):
                prog = {"chunk": idx, "total": len(chunks), "message": f"转写第 {idx}/{len(chunks)} 块"}
                (out_dir / "transcribe_progress.json").write_text(json.dumps(prog, ensure_ascii=False), encoding="utf-8")
                console.print(f"[cyan]转写分块[/cyan] {idx}/{len(chunks)}")
                part, info = _transcribe_whisper(model, chunk_path, cfg)
                for seg in part:
                    segments.append({
                        "start": seg["start"] + offset,
                        "end": seg["end"] + offset,
                        "text": seg["text"],
                    })
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    else:
        segments, info = _transcribe_whisper(model, video_path, cfg)

    replacements = load_terminology(cfg)
    segments = apply_to_segments(segments, replacements)
    segments = post_process_segments(segments, cfg)
    from .speaker_diarize import diarize_segments, format_srt_with_speaker

    segments = diarize_segments(segments, {**cfg, "diarization": {**(cfg.get("diarization") or {}), "audio_path": str(video_path)}})

    transcript = "\n".join(s["text"] for s in segments if s["text"])
    transcript = apply_replacements(transcript, replacements)
    srt_text = format_srt_with_speaker(segments) if any(s.get("speaker") for s in segments) else segments_to_srt(segments)

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
    from .subtitle_pdf import export_subtitle_pdf
    pdf = export_subtitle_pdf(segments, cfg, out_dir)
    if pdf:
        extra["pdf"] = pdf

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
