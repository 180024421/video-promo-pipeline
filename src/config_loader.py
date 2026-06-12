from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or ROOT / "config.yaml"
    if not cfg_path.exists():
        cfg_path = ROOT / "config.example.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def config_path() -> Path:
    p = ROOT / "config.yaml"
    return p if p.exists() else ROOT / "config.example.yaml"


def save_config(cfg: dict[str, Any], path: Path | None = None) -> Path:
    cfg_path = path or (ROOT / "config.yaml")
    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return cfg_path


def output_dir(cfg: dict[str, Any], job_name: str) -> Path:
    base = ROOT / cfg.get("output", {}).get("dir", "output")
    out = base / job_name
    out.mkdir(parents=True, exist_ok=True)
    return out
