from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from rich.console import Console

from .lm_client import call_lm, make_lm_client, parse_json_content
from .subtitle_burn import resolve_ffmpeg

console = Console()


def _build_clip_prompt(transcript: str, segments: list[dict[str, Any]], cfg: dict[str, Any], scene_hints: list[float] | None = None) -> str:
    scfg = cfg.get("smart_cut") or {}
    target = int(scfg.get("target_duration_sec", 90))
    min_clip = float(scfg.get("min_clip_sec", 3))
    style = scfg.get("style", "保留高潮、干货与结论，删除重复与长时间静音段")

    seg_preview = "\n".join(
        f'{s["start"]:.1f}-{s["end"]:.1f}s: {s.get("text", "")[:50]}'
        for s in segments[:100]
    )
    scene_block = ""
    if scene_hints:
        times = ", ".join(f"{t:.1f}s" for t in scene_hints[:30])
        scene_block = f"\n检测到以下转场/场景切换点（优先在切换点附近剪辑）：{times}\n"
    return textwrap.dedent(f"""\
        你是短视频剪辑师。根据转写内容，选出应保留的片段并输出 JSON（不要 markdown）。
        目标：剪成约 {target} 秒的精华版。
        策略：{style}
        规则：
        - clips 数组，每项含 start、end（秒，浮点）
        - 每段至少 {min_clip} 秒，按时间顺序，不要重叠
        - 总时长尽量接近 {target} 秒
        {scene_block}
        转写分段：
        ---
        {seg_preview}
        ---

        转写摘要（前 4000 字）：
        {transcript[:4000]}

        JSON 格式：
        {{"clips": [{{"start": 12.5, "end": 28.0, "reason": "核心演示"}}]}}
    """)


def generate_clip_plan(
    transcript: str,
    segments: list[dict[str, Any]],
    cfg: dict[str, Any],
    out_dir: Path,
    *,
    scene_hints: list[float] | None = None,
) -> list[dict[str, Any]]:
    scfg = cfg.get("smart_cut") or {}
    if not scfg.get("enabled", False):
        return []

    lcfg = cfg.get("lm_studio") or {}
    if not lcfg.get("enabled", True):
        console.print("[yellow]智能剪辑需要 LM Studio，已跳过[/yellow]")
        return []

    client = make_lm_client(cfg)
    prompt = _build_clip_prompt(transcript, segments, cfg, scene_hints)
    console.print("[cyan]LM Studio 智能剪辑规划...[/cyan]")
    content = call_lm(client, prompt, cfg, "你是专业的短视频剪辑师。")
    data = parse_json_content(content)
    clips = data.get("clips", []) if isinstance(data, dict) else []
    norm: list[dict[str, Any]] = []
    for c in clips:
        start = float(c.get("start", 0))
        end = float(c.get("end", 0))
        if end - start >= float(scfg.get("min_clip_sec", 3)):
            norm.append({"start": start, "end": end, "reason": c.get("reason", "")})
    (out_dir / "clip_plan.json").write_text(json.dumps({"clips": norm}, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]剪辑方案[/green] {len(norm)} 段")
    return norm


def apply_clip_plan(video_path: Path, clips: list[dict[str, Any]], cfg: dict[str, Any], out_dir: Path) -> Path | None:
    if not clips:
        return None

    ffmpeg = resolve_ffmpeg(cfg)
    out_path = out_dir / f"{video_path.stem}_smart{video_path.suffix}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        part_files: list[Path] = []
        for i, clip in enumerate(clips):
            part = tmp_dir / f"part_{i:03d}.mp4"
            cmd = [
                ffmpeg,
                "-y",
                "-ss",
                str(clip["start"]),
                "-to",
                str(clip["end"]),
                "-i",
                str(video_path),
                "-c",
                "copy",
                str(part),
            ]
            subprocess.run(cmd, check=True)
            part_files.append(part)

        list_file = tmp_dir / "concat.txt"
        list_file.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in part_files),
            encoding="utf-8",
        )
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)

    console.print(f"[green]智能剪辑完成[/green] {out_path}")
    return out_path
