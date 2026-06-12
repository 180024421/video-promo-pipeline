from __future__ import annotations

from typing import Any

PRESETS = {
    "fast": {"crf": 28, "preset": "veryfast", "audio_bitrate": "96k", "label": "快速（体积小）"},
    "balanced": {"crf": 23, "preset": "medium", "audio_bitrate": "128k", "label": "均衡（推荐）"},
    "quality": {"crf": 18, "preset": "slow", "audio_bitrate": "192k", "label": "高画质（体积大）"},
}


def resolve_quality(cfg: dict[str, Any]) -> dict[str, Any]:
    qcfg = cfg.get("video_quality") or {}
    name = qcfg.get("preset", "balanced")
    base = PRESETS.get(name, PRESETS["balanced"])
    return {
        **base,
        "crf": int(qcfg.get("crf", base["crf"])),
        "preset": qcfg.get("ffmpeg_preset", base["preset"]),
        "audio_bitrate": qcfg.get("audio_bitrate", base["audio_bitrate"]),
        "name": name,
    }


def ffmpeg_video_args(cfg: dict[str, Any]) -> list[str]:
    q = resolve_quality(cfg)
    return ["-c:v", "libx264", "-crf", str(q["crf"]), "-preset", q["preset"]]
