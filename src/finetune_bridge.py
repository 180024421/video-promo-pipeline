from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config_loader import ROOT

BRIDGE_PATH = ROOT / "data" / "finetune_bridge.json"


def load_bridge(path: Path | None = None) -> dict[str, Any] | None:
    p = path or BRIDGE_PATH
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def apply_bridge_to_config(cfg: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """若 finetune.auto_apply_bridge 为 true，将 bridge 推荐模型写入 lm_studio.model。"""
    fcfg = cfg.get("finetune") or {}
    if not force and not bool(fcfg.get("auto_apply_bridge", False)):
        return cfg

    bridge_file = fcfg.get("bridge_file") or "data/finetune_bridge.json"
    bridge_path = Path(bridge_file)
    if not bridge_path.is_absolute():
        bridge_path = ROOT / bridge_path

    bridge = load_bridge(bridge_path)
    if not bridge:
        return cfg

    model = bridge.get("recommended_lm_studio_model") or bridge.get("recommended_model") or ""
    if not model:
        return cfg

    lm = dict(cfg.get("lm_studio") or {})
    lm["model"] = model
    cfg = dict(cfg)
    cfg["lm_studio"] = lm
    cfg["finetune"] = {
        **fcfg,
        "active_bridge": str(bridge_path),
        "recommended_lora": bridge.get("recommended_lora", ""),
        "eval_score": bridge.get("eval_score"),
        "ab_winner": bridge.get("ab_winner"),
    }
    return cfg


def bridge_summary() -> dict[str, Any]:
    bridge = load_bridge()
    if not bridge:
        return {"available": False}
    return {
        "available": True,
        "updated_at": bridge.get("updated_at"),
        "recommended_lora": bridge.get("recommended_lora"),
        "recommended_model": bridge.get("recommended_lm_studio_model"),
        "eval_score": bridge.get("eval_score"),
        "ab_winner": bridge.get("ab_winner"),
        "reports": bridge.get("reports"),
        "train_samples": bridge.get("train_samples"),
        "eval_samples": bridge.get("eval_samples"),
    }
