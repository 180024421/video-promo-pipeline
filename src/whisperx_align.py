from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def align_segments_whisperx(video_path: Path, segments: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    wcfg = cfg.get("whisperx") or {}
    if not wcfg.get("enabled", False):
        return segments
    try:
        import whisperx  # type: ignore
    except ImportError:
        console.print("[yellow]WhisperX 未安装: pip install whisperx[/yellow]")
        return segments

    device = wcfg.get("device", (cfg.get("whisper") or {}).get("device", "cuda"))
    model_name = wcfg.get("model", (cfg.get("whisper") or {}).get("model", "small"))
    lang = (cfg.get("whisper") or {}).get("language", "zh")

    console.print(f"[cyan]WhisperX 对齐[/cyan] {model_name}")
    model = whisperx.load_model(model_name, device=device, compute_type="float16")
    audio = whisperx.load_audio(str(video_path))
    result = model.transcribe(audio, batch_size=16, language=lang)
    align_model, metadata = whisperx.load_align_model(language_code=lang, device=device)
    aligned = whisperx.align(result["segments"], align_model, metadata, audio, device, return_char_alignments=False)

    out: list[dict[str, Any]] = []
    for seg in aligned.get("segments", []):
        text = seg.get("text", "").strip()
        if not text:
            continue
        out.append({"start": float(seg["start"]), "end": float(seg["end"]), "text": text})
    if out:
        console.print(f"[green]WhisperX[/green] {len(out)} 段对齐")
        return out
    return segments
