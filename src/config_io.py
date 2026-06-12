from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .config_loader import ROOT, load_config, save_config


def export_config_bundle(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config()
    out = ROOT / "output" / f"config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return out


def import_config_bundle(path: Path, merge: bool = True) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if merge:
        base = load_config()
        data = _deep_merge(base, data)
    save_config(data)
    return data


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
