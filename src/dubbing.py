from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import probe_duration, resolve_ffmpeg, run_ffmpeg
from .transcribe import segments_to_srt
from .tts_engines import synthesize_all_segments

console = Console()


def build_timeline_audio(
    segments: list[dict[str, Any]],
    tts_dir: Path,
    video_duration: float,
    cfg: dict[str, Any],
    out_dir: Path,
) -> Path:
    ffmpeg = resolve_ffmpeg(cfg)
    dcfg = cfg.get("dubbing") or {}
    audio_mode = dcfg.get("timeline_mode", "continuous")
    out_audio = out_dir / "narration_audio.mp3"

    if audio_mode == "continuous" or len(segments) <= 1:
        tts_files = sorted(tts_dir.glob("seg_*.mp3"))
        list_file = out_dir / "tts_concat.txt"
        list_file.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in tts_files if p.exists()),
            encoding="utf-8",
        )
        run_ffmpeg([
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:a", "libmp3lame", "-q:a", "2", str(out_audio),
        ])
        return out_audio

    filter_parts: list[str] = []
    inputs = ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={max(video_duration, 1):.3f}"]
    input_labels: list[str] = []
    idx = 0
    for i, seg in enumerate(segments):
        if not (seg.get("text") or "").strip():
            continue
        tts_path = tts_dir / f"seg_{i:04d}.mp3"
        if not tts_path.exists():
            continue
        idx += 1
        inputs.extend(["-i", str(tts_path)])
        delay_ms = int(float(seg.get("start", 0)) * 1000)
        label = f"a{i}"
        filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms}[{label}]")
        input_labels.append(f"[{label}]")

    if not input_labels:
        raise RuntimeError("没有可用的 TTS 分段")
    mix_inputs = "".join(input_labels)
    filter_parts.append(f"{mix_inputs}amix=inputs={len(input_labels)}:duration=first[out]")
    run_ffmpeg([ffmpeg, "-y", *inputs, "-filter_complex", ";".join(filter_parts), "-map", "[out]", str(out_audio)])
    return out_audio


def _sync_av_durations(video_path: Path, audio_path: Path, cfg: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    """音画同步：配音比视频长时加速视频，短则保持 shortest。"""
    dcfg = cfg.get("dubbing") or {}
    mode = dcfg.get("sync_mode", "auto")
    if mode == "none":
        return video_path, audio_path

    vdur = probe_duration(cfg, video_path)
    adur = probe_duration(cfg, audio_path)
    if vdur <= 0 or adur <= 0:
        return video_path, audio_path

    ffmpeg = resolve_ffmpeg(cfg)
    if adur > vdur * 1.05 and mode in ("auto", "speed_video"):
        factor = adur / vdur
        synced = out_dir / f"{video_path.stem}_synced{video_path.suffix}"
        run_ffmpeg([
            ffmpeg, "-y", "-i", str(video_path),
            "-filter:v", f"setpts=PTS/{factor}",
            "-an", str(synced),
        ], desc=f"视频加速同步 x{factor:.2f}")
        return synced, audio_path

    if adur < vdur * 0.95 and mode in ("auto", "pad_audio"):
        padded = out_dir / "narration_audio_padded.mp3"
        pad_d = vdur - adur + 0.5
        run_ffmpeg([
            ffmpeg, "-y", "-i", str(audio_path),
            "-af", f"apad=pad_dur={pad_d}",
            str(padded),
        ], desc="音频补静音对齐")
        return video_path, padded

    return video_path, audio_path


def apply_dubbing(video_path: Path, audio_path: Path, cfg: dict[str, Any], out_dir: Path) -> Path:
    ffmpeg = resolve_ffmpeg(cfg)
    dcfg = cfg.get("dubbing") or {}
    mode = dcfg.get("audio_mode", "replace")
    orig_vol = float(dcfg.get("original_volume", 0.15))
    out_path = out_dir / f"{video_path.stem}_dubbed{video_path.suffix}"

    if mode == "keep_original":
        shutil.copy2(video_path, out_path)
        return out_path

    video_path, audio_path = _sync_av_durations(video_path, audio_path, cfg, out_dir)

    if mode == "mix":
        cmd = [
            ffmpeg, "-y", "-i", str(video_path), "-i", str(audio_path),
            "-filter_complex",
            f"[0:a]volume={orig_vol}[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:duration=first[outa]",
            "-map", "0:v", "-map", "[outa]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path),
        ]
    else:
        cmd = [
            ffmpeg, "-y", "-i", str(video_path), "-i", str(audio_path),
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path),
        ]
    run_ffmpeg(cmd, desc=f"配音混流 mode={mode}")
    return out_path


def narration_to_srt(narration: dict[str, Any], out_dir: Path) -> Path:
    srt_path = out_dir / "narration.srt"
    srt_path.write_text(segments_to_srt(narration.get("segments") or []), encoding="utf-8")
    return srt_path


def run_dubbing(video_path: Path, narration: dict[str, Any], cfg: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    dcfg = cfg.get("dubbing") or {}
    if not dcfg.get("enabled", True):
        return {"enabled": False}

    segments = narration.get("segments") or []
    if not segments:
        return {"enabled": False}

    tts_dir = synthesize_all_segments(segments, cfg, out_dir)
    vdur = probe_duration(cfg, video_path)
    audio_path = build_timeline_audio(segments, tts_dir, vdur, cfg, out_dir)
    dubbed = apply_dubbing(video_path, audio_path, cfg, out_dir)
    srt_path = narration_to_srt(narration, out_dir)

    meta = {
        "enabled": True,
        "dubbed_video": str(dubbed),
        "narration_audio": str(audio_path),
        "narration_srt": str(srt_path),
        "segment_count": len(segments),
        "engine": dcfg.get("engine", "edge-tts"),
    }
    (out_dir / "dubbing.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
