from __future__ import annotations

from typing import Any

from rich.console import Console

console = Console()


def release_gpu_if_needed(cfg: dict[str, Any], label: str = "") -> None:
    """步骤间释放 GPU 缓存（受 whisper.clear_gpu_cache 与 gpu_budget 控制）。"""
    gcfg = cfg.get("gpu_budget") or {}
    if not gcfg.get("release_between_steps", True):
        return
    wcfg = cfg.get("whisper") or {}
    if not wcfg.get("clear_gpu_cache", True) and not gcfg.get("force_release", False):
        return
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if label:
                console.print(f"[dim]GPU 缓存已释放[/dim] ({label})")
    except Exception:
        pass
