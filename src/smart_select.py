from __future__ import annotations

import json
import textwrap
from typing import Any

from rich.console import Console

from .lm_client import call_lm, make_lm_client, parse_json_content

console = Console()


def pick_highlight_window(
    transcript: str,
    segments: list[dict[str, Any]],
    cfg: dict[str, Any],
    *,
    clip_len: int,
    video_duration: float,
) -> tuple[float, float]:
    """返回 (start_sec, duration_sec) 用于竖屏切片。"""
    ccfg = cfg.get("clip_short") or {}
    sscfg = ccfg.get("smart_select") or {}
    min_d = float(sscfg.get("min_clip_duration", 30))
    max_d = float(sscfg.get("max_clip_duration", clip_len))
    target = min(clip_len, max_d)

    lcfg = cfg.get("lm_studio") or {}
    if not sscfg.get("enabled", False) or not lcfg.get("enabled", True):
        return 0.0, float(target)

    seg_preview = "\n".join(
        f'{s["start"]:.1f}-{s["end"]:.1f}s: {s.get("text", "")[:50]}'
        for s in segments[:80]
    )
    prompt = textwrap.dedent(f"""\
        你是短视频剪辑师。从以下转写中选出最适合做竖屏短视频的连续片段。
        要求：
        - 输出 JSON，不要 markdown
        - start: 起始秒（浮点）
        - duration: 时长秒，范围 {min_d}-{target}，尽量接近 {target}
        - reason: 一句话说明
        - 片段应在 0 ~ {video_duration:.1f} 秒内

        转写分段：
        {seg_preview}

        全文前 3000 字：
        {transcript[:3000]}

        JSON: {{"start": 12.5, "duration": 75, "reason": "..."}}
    """)
    try:
        client = make_lm_client(cfg)
        content = call_lm(client, prompt, cfg, "你是专业的短视频剪辑师。")
        data = parse_json_content(content)
        if isinstance(data, dict):
            start = max(0.0, float(data.get("start", 0)))
            dur = float(data.get("duration", target))
            dur = max(min_d, min(dur, max_d, video_duration - start))
            console.print(f"[green]AI 选段[/green] {start:.1f}s + {dur:.1f}s — {data.get('reason', '')}")
            return start, dur
    except Exception as e:
        console.print(f"[yellow]AI 选段失败，使用默认: {e}[/yellow]")
    return 0.0, float(target)


def pick_multiple_highlight_windows(
    transcript: str,
    segments: list[dict[str, Any]],
    cfg: dict[str, Any],
    *,
    clip_len: int,
    video_duration: float,
    count: int = 3,
) -> list[tuple[float, float]]:
    ccfg = cfg.get("clip_short") or {}
    sscfg = ccfg.get("smart_select") or {}
    min_d = float(sscfg.get("min_clip_duration", 30))
    max_d = float(sscfg.get("max_clip_duration", clip_len))
    target = min(clip_len, max_d)
    count = max(1, min(count, 5))

    lcfg = cfg.get("lm_studio") or {}
    if not sscfg.get("enabled", False) or not lcfg.get("enabled", True) or count <= 1:
        start, dur = pick_highlight_window(transcript, segments, cfg, clip_len=clip_len, video_duration=video_duration)
        return [(start, dur)]

    seg_preview = "\n".join(
        f'{s["start"]:.1f}-{s["end"]:.1f}s: {s.get("text", "")[:50]}'
        for s in segments[:100]
    )
    prompt = textwrap.dedent(f"""\
        从转写中选出 {count} 个互不重叠的竖屏高光片段。
        输出 JSON 数组 [{{"start":0,"duration":75,"reason":""}}]
        duration 范围 {min_d}-{target}s，视频总长 {video_duration:.1f}s。

        分段：{seg_preview}
        全文：{transcript[:2500]}
    """)
    try:
        client = make_lm_client(cfg)
        content = call_lm(client, prompt, cfg, "你是专业的短视频剪辑师。")
        data = parse_json_content(content)
        items = data if isinstance(data, list) else (data.get("clips") or []) if isinstance(data, dict) else []
        windows: list[tuple[float, float]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            start = max(0.0, float(item.get("start", 0)))
            dur = max(min_d, min(float(item.get("duration", target)), max_d, video_duration - start))
            windows.append((start, dur))
        if windows:
            console.print(f"[green]AI 多段选片[/green] {len(windows)} 段")
            return windows[:count]
    except Exception as e:
        console.print(f"[yellow]AI 多段选片失败: {e}[/yellow]")
    start, dur = pick_highlight_window(transcript, segments, cfg, clip_len=clip_len, video_duration=video_duration)
    return [(start, dur)]
