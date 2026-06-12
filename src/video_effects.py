from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import escape_sub_path, probe_duration, resolve_ffmpeg, run_ffmpeg

console = Console()

_WATERMARK_POS = {
    "top-left": "x=20:y=20",
    "top-right": "x=w-tw-20:y=20",
    "bottom-left": "x=20:y=h-th-20",
    "bottom-right": "x=w-tw-20:y=h-th-20",
}


def build_watermark_filter(cfg: dict[str, Any]) -> str:
    wcfg = (cfg.get("clip_short") or {}).get("watermark") or {}
    if not wcfg.get("enabled", False):
        return ""
    text = wcfg.get("text", "@账号").replace(":", "\\:").replace("'", "\\'")
    opacity = float(wcfg.get("opacity", 0.6))
    pos = _WATERMARK_POS.get(wcfg.get("position", "bottom-right"), _WATERMARK_POS["bottom-right"])
    return f"drawtext=text='{text}':fontsize=28:fontcolor=white@{opacity}:{pos}"


def mix_bgm_on_video(
    video_path: Path,
    cfg: dict[str, Any],
    out_path: Path,
    segments: list[dict[str, Any]] | None = None,
) -> Path:
    bgm_cfg = (cfg.get("clip_short") or {}).get("bgm") or {}
    if not bgm_cfg.get("enabled", False):
        return video_path
    bgm_file = bgm_cfg.get("file", "")
    if not bgm_file or not Path(bgm_file).exists():
        console.print("[yellow]BGM 文件不存在，跳过[/yellow]")
        return video_path

    ffmpeg = resolve_ffmpeg(cfg)
    vol = float(bgm_cfg.get("volume", 0.15))
    fade = float(bgm_cfg.get("fade_out_sec", 2.0))
    duck = bool(bgm_cfg.get("ducking", True))
    dur = probe_duration(cfg, video_path)
    fade_start = max(0.0, dur - fade)

    if duck:
        filter_complex = (
            f"[1:a]volume={vol}[bgm];"
            f"[0:a][bgm]sidechaincompressor=threshold=0.02:ratio=8:attack=200:release=800[outa]"
        )
    else:
        filter_complex = (
            f"[0:a]volume=1.0[a0];"
            f"[1:a]volume={vol},afade=t=out:st={fade_start}:d={fade}[bgm];"
            f"[a0][bgm]amix=inputs=2:duration=first:dropout_transition=2[outa]"
        )

    cmd = [
        ffmpeg, "-y",
        "-i", str(video_path),
        "-i", str(bgm_file),
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[outa]",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(out_path),
    ]
    run_ffmpeg(cmd, desc="BGM 混音" + (" (ducking)" if duck else ""))
    return out_path


def build_fancy_ass(srt_path: Path, cfg: dict[str, Any], out_dir: Path) -> Path:
    """生成竖屏花字 ASS（大字 + 描边）。"""
    ccfg = (cfg.get("clip_short") or {}).get("caption_style") or {}
    if not ccfg.get("enabled", False):
        return srt_path

    from .transcribe import segments_to_srt

    # 读取 srt 简单解析为 segments
    segments: list[dict[str, Any]] = []
    lines = srt_path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().isdigit() and i + 2 < len(lines):
            times = lines[i + 1]
            if "-->" in times:
                start_s, end_s = times.split("-->")
                def _parse_ts(ts: str) -> float:
                    ts = ts.strip().replace(",", ".")
                    p = ts.split(":")
                    if len(p) == 3:
                        return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
                    return 0.0
                segments.append({
                    "start": _parse_ts(start_s),
                    "end": _parse_ts(end_s),
                    "text": lines[i + 2].strip(),
                })
                i += 4
                continue
        i += 1

    fs = int(ccfg.get("font_size", 56))
    color = ccfg.get("color", "#FFFFFF").lstrip("#")
    stroke = ccfg.get("stroke_color", "#000000").lstrip("#")
    sw = int(ccfg.get("stroke_width", 4))

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Fancy,Microsoft YaHei,{fs},&H00{color[4:6]}{color[2:4]}{color[0:2]},&H000000FF,&H00{stroke[4:6]}{stroke[2:4]}{stroke[0:2]},&H00000000,1,0,0,0,100,100,0,0,1,{sw},0,2,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _ass_ts(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    events: list[str] = []
    for seg in segments:
        events.append(
            f"Dialogue: 0,{_ass_ts(seg['start'])},{_ass_ts(seg['end'])},Fancy,,0,0,0,,{seg['text']}"
        )

    ass_path = out_dir / "fancy_captions.ass"
    ass_path.write_text(header + "\n".join(events), encoding="utf-8")
    return ass_path


def burn_fancy_subtitles(video_path: Path, subtitle_path: Path, cfg: dict[str, Any], out_path: Path) -> Path:
    ffmpeg = resolve_ffmpeg(cfg)
    sub_esc = escape_sub_path(subtitle_path)
    cmd = [
        ffmpeg, "-y", "-i", str(video_path),
        "-vf", f"subtitles='{sub_esc}'",
        "-c:a", "copy", str(out_path),
    ]
    run_ffmpeg(cmd, desc="花字字幕烧录")
    return out_path
