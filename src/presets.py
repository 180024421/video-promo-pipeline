from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .config_loader import ROOT

PRESETS_DIR = ROOT / "templates" / "presets"


def list_presets() -> list[dict[str, str]]:
    if not PRESETS_DIR.exists():
        return []
    items: list[dict[str, str]] = []
    for p in sorted(PRESETS_DIR.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        items.append({
            "id": p.stem,
            "name": data.get("name", p.stem),
            "description": data.get("description", ""),
        })
    return items


def apply_preset(cfg: dict[str, Any], preset_id: str) -> dict[str, Any]:
    path = PRESETS_DIR / f"{preset_id}.yaml"
    if not path.exists():
        return cfg
    preset = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overlay = preset.get("config") or {}
    merged = deepcopy(cfg)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **val}
        else:
            merged[key] = val
    merged.setdefault("workflow", {})["preset"] = preset_id
    return merged


def load_config_with_preset(config_path: Path | None, preset_id: str | None = None) -> dict[str, Any]:
    from .config_loader import load_config

    cfg = load_config(config_path)
    pid = preset_id or (cfg.get("workflow") or {}).get("preset")
    if pid:
        cfg = apply_preset(cfg, pid)
    return cfg
