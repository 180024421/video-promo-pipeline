from __future__ import annotations

import shutil
import urllib.request
from typing import Any

from rich.console import Console

console = Console()


def check_ffmpeg(cfg: dict[str, Any]) -> bool:
    custom = (cfg.get("ffmpeg") or {}).get("path") or ""
    if custom:
        return True
    ok = shutil.which("ffmpeg") is not None
    if not ok:
        console.print("[red]缺少 FFmpeg[/red] https://ffmpeg.org/download.html")
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
            return resp.status == 200
    except Exception:
        console.print("[yellow]LM Studio 未就绪，文案步骤将跳过或失败[/yellow]")
        console.print("[yellow]请启动 LM Studio Local Server[/yellow]")
        return False


def run_preflight(cfg: dict[str, Any], *, need_lm: bool = True) -> bool:
    console.print("[bold]环境检查[/bold]")
    ok = True
    ok = check_ffmpeg(cfg) and ok
    ok = check_auto_editor(cfg) and ok
    if need_lm and (cfg.get("lm_studio") or {}).get("enabled", True):
        check_lm_studio(cfg)
    try:
        import faster_whisper  # noqa: F401
        console.print("[green]✓[/green] faster-whisper")
    except ImportError:
        console.print("[red]缺少 faster-whisper[/red]")
        ok = False
    return ok
