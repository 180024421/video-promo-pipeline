from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import probe_duration, resolve_ffmpeg, run_ffmpeg
from .lm_client import call_lm, make_lm_client, parse_json_content

console = Console()


def detect_broll_markers(transcript: str, segments: list[dict[str, Any]], cfg: dict[str, Any], out_dir: Path) -> list[dict[str, Any]]:
    bcfg = cfg.get("broll") or {}
    if not bcfg.get("enabled", False):
        return []

    lcfg = cfg.get("lm_studio") or {}
    if not lcfg.get("enabled", True):
        return []

    seg_preview = "\n".join(f'{s["start"]:.1f}s: {s.get("text","")[:50]}' for s in segments[:60])
    prompt = textwrap.dedent(f"""\
        分析转写，标记适合插入 B-roll 配图/截图的位置。
        输出 JSON 数组，每项：start(秒), duration(秒,2-5), asset_hint(素材描述,如"代码截图","架构图")
        不要 markdown。最多 5 个。

        转写：
        {seg_preview}
        {transcript[:4000]}
    """)
    try:
        client = make_lm_client(cfg)
        content = call_lm(client, prompt, cfg, "你是视频剪辑助手。")
        data = parse_json_content(content)
        markers = data if isinstance(data, list) else data.get("markers", []) if isinstance(data, dict) else []
        norm = [
            {
                "start": float(m.get("start", 0)),
                "duration": float(m.get("duration", 3)),
                "asset_hint": m.get("asset_hint", ""),
                "asset_path": "",
            }
            for m in markers
        ]
        (out_dir / "broll_markers.json").write_text(json.dumps(norm, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]B-roll 标记[/green] {len(norm)} 处")
        return norm
    except Exception as e:
        console.print(f"[yellow]B-roll 分析失败: {e}[/yellow]")
        return []


def _resolve_asset(hint: str, cfg: dict[str, Any]) -> Path | None:
    assets_dir = Path((cfg.get("broll") or {}).get("assets_dir", "assets/broll"))
    if not assets_dir.is_absolute():
        from .config_loader import ROOT
        assets_dir = ROOT / assets_dir
    if not assets_dir.exists():
        return None
    hint_lower = hint.lower()
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        for p in assets_dir.glob(ext):
            if hint_lower in p.stem.lower() or not hint:
                return p
    imgs = list(assets_dir.glob("*.*"))
    return imgs[0] if imgs else None


def apply_broll(video_path: Path, markers: list[dict[str, Any]], cfg: dict[str, Any], out_dir: Path) -> Path | None:
    if not markers:
        return None

    ffmpeg = resolve_ffmpeg(cfg)
    out_path = out_dir / f"{video_path.stem}_broll{video_path.suffix}"
    dur = probe_duration(cfg, video_path)

    # 简化：取第一个有效 marker 做图片 overlay
    for m in markers:
        asset = _resolve_asset(m.get("asset_hint", ""), cfg)
        if asset is None:
            continue
        start = float(m.get("start", 0))
        overlay_d = float(m.get("duration", 3))
        enable = f"between(t\\,{start}\\,{start + overlay_d})"
        vf = (
            f"[1:v]scale=iw*0.8:-1[ov];"
            f"[0:v][ov]overlay=(W-w)/2:(H-h)/2:enable='{enable}'"
        )
        cmd = [
            ffmpeg, "-y",
            "-i", str(video_path),
            "-i", str(asset),
            "-filter_complex", vf,
            "-c:a", "copy",
            "-t", str(dur),
            str(out_path),
        ]
        run_ffmpeg(cmd, desc=f"B-roll 叠加 {asset.name}")
        return out_path
    console.print("[yellow]无可用 B-roll 素材[/yellow]")
    return None
