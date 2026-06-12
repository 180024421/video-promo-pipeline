from __future__ import annotations

import gc
from typing import Any, Callable

from rich.console import Console

console = Console()


def after_whisper(cfg: dict[str, Any]) -> None:
    """Whisper 完成后释放 GPU，为 LM Studio 让路。"""
    wcfg = cfg.get("whisper") or {}
    sched = (cfg.get("workflow") or {}).get("gpu_schedule", True)
    if not sched and not wcfg.get("clear_gpu_cache", True):
        return
    if wcfg.get("clear_gpu_cache") is False and not sched:
        return
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            console.print("[dim]GPU 缓存已释放，可安全启动 LM Studio[/dim]")
    except ImportError:
        pass


def run_lm_step(cfg: dict[str, Any], fn: Callable[[], Any]) -> Any:
    after_whisper(cfg)
    return fn()
