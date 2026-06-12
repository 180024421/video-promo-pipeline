from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import FFMPEG_INSTALL_HINT

console = Console()


def check_ffmpeg(cfg: dict[str, Any]) -> bool:
    custom = (cfg.get("ffmpeg") or {}).get("path") or ""
    if custom:
        ok = Path(custom).exists()
        if not ok:
            console.print(f"[red]ffmpeg.path 无效[/red] {custom}")
            console.print(FFMPEG_INSTALL_HINT)
        else:
            console.print(f"[green]✓[/green] FFmpeg ({custom})")
        return ok
    ok = shutil.which("ffmpeg") is not None
    if ok:
        console.print("[green]✓[/green] FFmpeg")
    else:
        console.print(f"[red]缺少 FFmpeg[/red]\n{FFMPEG_INSTALL_HINT}")
    return ok


def check_auto_editor(cfg: dict[str, Any]) -> bool:
    if not (cfg.get("auto_editor") or {}).get("enabled", True):
        return True
    ok = shutil.which("auto-editor") is not None
    if not ok:
        console.print("[yellow]未安装 auto-editor，将跳过粗剪[/yellow]")
    return True


def check_lm_studio(cfg: dict[str, Any]) -> bool:
    if not (cfg.get("lm_studio") or {}).get("enabled", True):
        return True
    base = (cfg.get("lm_studio") or {}).get("base_url", "http://127.0.0.1:1234/v1")
    url = base.rstrip("/").removesuffix("/v1") + "/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            if resp.status == 200:
                console.print("[green]✓[/green] LM Studio")
                return True
    except Exception:
        pass
    console.print("[yellow]LM Studio 未就绪[/yellow]")
    return False


def check_edge_tts(cfg: dict[str, Any]) -> bool:
    dcfg = cfg.get("dubbing") or {}
    ncfg = cfg.get("narration") or {}
    if not ncfg.get("enabled", False):
        return True
    if dcfg.get("engine", "edge-tts") != "edge-tts":
        console.print(f"[green]✓[/green] TTS engine={dcfg.get('engine')}")
        return True
    try:
        import edge_tts  # noqa: F401
        console.print("[green]✓[/green] edge-tts")
        return True
    except ImportError:
        console.print("[red]缺少 edge-tts[/red]")
        return False


def run_preflight(cfg: dict[str, Any], *, need_lm: bool = True) -> bool:
    console.print("[bold]环境检查[/bold]")
    ok = check_ffmpeg(cfg) and True
    check_auto_editor(cfg)
    ok = check_edge_tts(cfg) and ok
    need_lm = need_lm or (cfg.get("narration") or {}).get("enabled", False)
    need_lm = need_lm or (cfg.get("smart_cut") or {}).get("enabled", False)
    need_lm = need_lm or (cfg.get("vision") or {}).get("enabled", False)
    if need_lm:
        check_lm_studio(cfg)
    try:
        import faster_whisper  # noqa: F401
        console.print("[green]✓[/green] faster-whisper")
    except ImportError:
        console.print("[red]缺少 faster-whisper[/red]")
        ok = False
    presets = cfg.get("workflow", {}).get("preset")
    if presets:
        console.print(f"[dim]工作流预设: {presets}[/dim]")
    return ok
