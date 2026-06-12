from __future__ import annotations

from pathlib import Path
from typing import Any

from .config_loader import ROOT


def resolve_output_dir(cfg: dict[str, Any], tenant_id: str = "") -> Path:
    """简易租户隔离：output/{tenant_id}/。"""
    tcfg = cfg.get("tenant") or {}
    if not tcfg.get("enabled", False) or not tenant_id:
        base = cfg.get("output", {}).get("dir", "output")
        return ROOT / base
    return ROOT / tcfg.get("base_dir", "output") / tenant_id
