from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from .config_loader import ROOT

console = Console()

FFMPEG_INSTALL_HINT = (
    "Windows 安装 FFmpeg：\n"
    "  1. 下载 https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip\n"
    "  2. 解压后将 bin 目录加入系统 PATH\n"
    "  3. 或在 config.yaml 设置 ffmpeg.path: C:/ffmpeg/bin/ffmpeg.exe"
)


def resolve_ffmpeg(cfg: dict[str, Any]) -> str:
    custom = (cfg.get("ffmpeg") or {}).get("path") or ""
    if custom:
        p = Path(custom)
        if p.exists():
            return str(p)
        raise RuntimeError(f"ffmpeg.path 不存在: {custom}\n{FFMPEG_INSTALL_HINT}")
    found = shutil.which("ffmpeg")
    if found:
        return found
    bundled = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    raise RuntimeError(f"未找到 ffmpeg\n{FFMPEG_INSTALL_HINT}")


def probe_duration(cfg: dict[str, Any], path: Path) -> float:
    ffmpeg = resolve_ffmpeg(cfg)
    proc = subprocess.run(
        [ffmpeg, "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", proc.stderr or "")
    if not m:
        return 0.0
    h, mnt, sec = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(sec)


def probe_media(cfg: dict[str, Any], path: Path) -> dict[str, Any]:
    ffmpeg = resolve_ffmpeg(cfg)
    proc = subprocess.run(
        [ffmpeg, "-i", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    stderr = proc.stderr or ""
    duration = probe_duration(cfg, path)
    has_video = "Video:" in stderr
    has_audio = "Audio:" in stderr
    w, h = 0, 0
    vm = re.search(r"Video:.*\s(\d+)x(\d+)", stderr)
    if vm:
        w, h = int(vm.group(1)), int(vm.group(2))
    return {"duration": duration, "has_video": has_video, "has_audio": has_audio, "width": w, "height": h}


def run_ffmpeg(cmd: list[str], *, desc: str = "") -> None:
    if desc:
        console.print(f"[cyan]{desc}[/cyan]")
    subprocess.run(cmd, check=True)


def escape_sub_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:")
