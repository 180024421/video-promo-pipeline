from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def run_auto_editor(video_path: Path, cfg: dict[str, Any], out_dir: Path) -> Path | None:
    acfg = cfg.get("auto_editor", {})
    if not acfg.get("enabled", True):
        console.print("[yellow]已跳过 Auto-Editor 粗剪[/yellow]")
        return None

    if shutil.which("auto-editor") is None:
        console.print("[yellow]未找到 auto-editor，跳过粗剪。安装: pip install auto-editor[/yellow]")
        return None

    threshold = acfg.get("silent_threshold", 0.04)
    out_path = out_dir / f"{video_path.stem}_cut{video_path.suffix}"

    cmd = [
        "auto-editor",
        str(video_path),
        "--edit",
        "audio",
        "--frame_rate",
        "30",
        "--output",
        str(out_path),
        "--silent_threshold",
        str(threshold),
    ]

    console.print(f"[cyan]Auto-Editor 粗剪[/cyan] threshold={threshold}")
    subprocess.run(cmd, check=True)
    console.print(f"[green]粗剪完成[/green] {out_path}")
    return out_path
