from __future__ import annotations

from typing import Any

from rich.console import Console

console = Console()


def diarize_segments(segments: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """说话人标注：优先 pyannote，回退为静音间隔交替说话人。"""
    dcfg = cfg.get("diarization") or {}
    if not dcfg.get("enabled", False):
        return segments

    audio_path = dcfg.get("audio_path")
    if audio_path:
        try:
            return _pyannote_diarize(segments, audio_path, cfg)
        except Exception as e:
            console.print(f"[yellow]pyannote 不可用，使用启发式: {e}[/yellow]")

    return _heuristic_diarize(segments, cfg)


def _heuristic_diarize(segments: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    gap = float((cfg.get("diarization") or {}).get("speaker_gap_sec", 1.8))
    speaker = "说话人A"
    out: list[dict[str, Any]] = []
    prev_end = 0.0
    for seg in segments:
        s = dict(seg)
        if float(seg.get("start", 0)) - prev_end > gap:
            speaker = "说话人B" if speaker == "说话人A" else "说话人A"
        s["speaker"] = speaker
        out.append(s)
        prev_end = float(seg.get("end", prev_end))
    console.print(f"[green]说话人标注[/green] 启发式 {len(out)} 段")
    return out


def _pyannote_diarize(segments: list[dict[str, Any]], audio_path: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    from pyannote.audio import Pipeline  # type: ignore

    token = (cfg.get("diarization") or {}).get("hf_token", "")
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token or True)
    diar = pipeline(audio_path)
    labeled: list[dict[str, Any]] = []
    for seg in segments:
        s = dict(seg)
        mid = (float(seg["start"]) + float(seg["end"])) / 2
        spk = "说话人A"
        for turn, _, speaker in diar.itertracks(yield_label=True):
            if turn.start <= mid <= turn.end:
                spk = str(speaker)
                break
        s["speaker"] = spk
        labeled.append(s)
    return labeled


def format_srt_with_speaker(segments: list[dict[str, Any]]) -> str:
    from .transcribe import segments_to_srt

    enriched = []
    for seg in segments:
        s = dict(seg)
        spk = s.get("speaker")
        if spk and spk not in s.get("text", ""):
            s["text"] = f"[{spk}] {s['text']}"
        enriched.append(s)
    return segments_to_srt(enriched)
