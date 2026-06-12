from __future__ import annotations

import base64
import json
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import probe_duration, resolve_ffmpeg
from .lm_client import call_lm, make_lm_client, parse_json_content

console = Console()


def extract_keyframes(video_path: Path, cfg: dict[str, Any], out_dir: Path, count: int = 6) -> list[Path]:
    ffmpeg = resolve_ffmpeg(cfg)
    frames_dir = out_dir / "vision_frames"
    frames_dir.mkdir(exist_ok=True)
    dur = probe_duration(cfg, video_path)
    if dur <= 0:
        dur = 60.0
    step = dur / (count + 1)
    paths: list[Path] = []
    for i in range(count):
        ts = step * (i + 1)
        out = frames_dir / f"frame_{i:03d}.jpg"
        subprocess.run(
            [ffmpeg, "-y", "-ss", str(ts), "-i", str(video_path), "-vframes", "1", "-q:v", "2", str(out)],
            check=True,
            capture_output=True,
        )
        if out.exists():
            paths.append(out)
    return paths


def _vision_chat(frames: list[Path], prompt: str, cfg: dict[str, Any]) -> str:
    vcfg = cfg.get("vision") or {}
    model = vcfg.get("model") or (cfg.get("lm_studio") or {}).get("model") or ""
    client = make_lm_client(cfg)

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for fp in frames[: int(vcfg.get("frame_count", 6))]:
        b64 = base64.standard_b64encode(fp.read_bytes()).decode("ascii")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    kwargs: dict[str, Any] = {
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.3,
        "max_tokens": 2048,
        "timeout": (cfg.get("lm_studio") or {}).get("timeout", 120),
    }
    if model:
        kwargs["model"] = model
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def enhance_clip_plan_with_vision(
    video_path: Path,
    transcript: str,
    segments: list[dict[str, Any]],
    cfg: dict[str, Any],
    out_dir: Path,
) -> list[dict[str, Any]]:
    vcfg = cfg.get("vision") or {}
    if not vcfg.get("enabled", False):
        return []

    frames = extract_keyframes(video_path, cfg, out_dir, int(vcfg.get("frame_count", 6)))
    if not frames:
        return []

    seg_preview = "\n".join(f'{s["start"]:.1f}s: {s.get("text","")[:40]}' for s in segments[:40])
    prompt = textwrap.dedent(f"""\
        你是视频内容分析师。结合截图与转写，选出最有视觉冲击力和信息密度的片段用于短视频。
        转写摘要：
        {seg_preview}
        转写前2000字：{transcript[:2000]}
        输出 JSON：{{"clips":[{{"start":0,"end":30,"reason":"画面+内容亮点"}}]}}
        不要 markdown。
    """)
    try:
        console.print("[cyan]视觉模型分析画面...[/cyan]")
        content = _vision_chat(frames, prompt, cfg)
        data = parse_json_content(content)
        clips = data.get("clips", []) if isinstance(data, dict) else []
        norm = [
            {"start": float(c["start"]), "end": float(c["end"]), "reason": c.get("reason", "vision")}
            for c in clips
            if float(c.get("end", 0)) - float(c.get("start", 0)) >= 3
        ]
        pending_path = out_dir / "vision_clip_plan_pending.json"
        pending_path.write_text(json.dumps({"clips": norm, "status": "pending"}, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "vision_clip_plan.json").write_text(json.dumps({"clips": norm}, ensure_ascii=False, indent=2), encoding="utf-8")

        if vcfg.get("require_confirmation", False):
            confirmed = out_dir / "vision_confirmed.json"
            if not confirmed.exists():
                console.print("[yellow]视觉剪辑方案待确认[/yellow] 请在 Web 面板批准后再重跑智能剪辑")
                return []
        return norm
    except Exception as e:
        console.print(f"[yellow]视觉分析失败，回退文本剪辑: {e}[/yellow]")
        return []
