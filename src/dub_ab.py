from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from rich.console import Console

from .dubbing import run_dubbing

console = Console()


def run_dub_ab_comparison(
    video_path: Path,
    narration: dict[str, Any],
    cfg: dict[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    """生成两种音色的配音版本供对比。"""
    dcfg = cfg.get("dubbing") or {}
    voices = dcfg.get("ab_voices") or [
        dcfg.get("voice", "zh-CN-YunxiNeural"),
        "zh-CN-XiaoxiaoNeural",
    ]
    if len(voices) < 2:
        voices = [voices[0], "zh-CN-XiaoxiaoNeural"]

    results: list[dict[str, Any]] = []
    for i, voice in enumerate(voices[:2]):
        label = f"voice_{chr(65 + i)}"
        sub_dir = out_dir / f"dub_ab_{label}"
        sub_dir.mkdir(exist_ok=True)
        cfg_v = copy.deepcopy(cfg)
        cfg_v.setdefault("dubbing", {})["voice"] = voice
        cfg_v["dubbing"]["engine"] = "edge-tts"
        console.print(f"[cyan]AB 配音[/cyan] {label} = {voice}")
        meta = run_dubbing(video_path, narration, cfg_v, sub_dir)
        results.append({"label": label, "voice": voice, "meta": meta, "dir": str(sub_dir)})

    summary = {"variants": results}
    (out_dir / "dub_ab.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
