from __future__ import annotations

import shutil
from typing import Any

PRESETS = {
    "fast": {"crf": 28, "preset": "veryfast", "audio_bitrate": "96k", "nvenc_preset": "p5", "label": "快速（体积小）"},
    "balanced": {"crf": 23, "preset": "medium", "audio_bitrate": "128k", "nvenc_preset": "p4", "label": "均衡（推荐）"},
    "quality": {"crf": 18, "preset": "slow", "audio_bitrate": "192k", "nvenc_preset": "p3", "label": "高画质（体积大）"},
}


def _nvenc_available() -> bool:
    return shutil.which("ffmpeg") is not None


def resolve_quality(cfg: dict[str, Any]) -> dict[str, Any]:
    qcfg = cfg.get("video_quality") or {}
    name = qcfg.get("preset", "balanced")
    base = PRESETS.get(name, PRESETS["balanced"])
    encoder = qcfg.get("encoder", "libx264")
    if encoder == "h264_nvenc" and not qcfg.get("force_nvenc", False):
        encoder = "h264_nvenc"
    return {
        **base,
        "crf": int(qcfg.get("crf", base["crf"])),
        "preset": qcfg.get("ffmpeg_preset", base["preset"]),
        "audio_bitrate": qcfg.get("audio_bitrate", base["audio_bitrate"]),
        "nvenc_preset": qcfg.get("nvenc_preset", base["nvenc_preset"]),
        "encoder": encoder,
        "name": name,
    }


def ffmpeg_video_args(cfg: dict[str, Any], *, copy_video: bool = False) -> list[str]:
    if copy_video:
        return ["-c:v", "copy"]
    q = resolve_quality(cfg)
    if q["encoder"] == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", q["nvenc_preset"], "-cq", str(q["crf"])]
    return ["-c:v", "libx264", "-crf", str(q["crf"]), "-preset", q["preset"]]


def ffmpeg_audio_args(cfg: dict[str, Any], *, copy_audio: bool = False) -> list[str]:
    if copy_audio:
        return ["-c:a", "copy"]
    q = resolve_quality(cfg)
    return ["-c:a", "aac", "-b:a", q["audio_bitrate"]]
