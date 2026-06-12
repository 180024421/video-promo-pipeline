from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .config_loader import ROOT


def load_terminology(cfg: dict[str, Any]) -> dict[str, str]:
    tcfg = cfg.get("terminology") or {}
    if not tcfg.get("enabled", True):
        return {}
    path = ROOT / tcfg.get("file", "terminology.yaml")
    if not path.exists():
        path = ROOT / "terminology.example.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    reps = data.get("replacements") or {}
    return {str(k): str(v) for k, v in reps.items()}


def apply_replacements(text: str, replacements: dict[str, str]) -> str:
    if not replacements or not text:
        return text
    result = text
    for wrong, right in replacements.items():
        if not wrong:
            continue
        result = re.sub(re.escape(wrong), right, result, flags=re.IGNORECASE)
    return result


def apply_to_segments(segments: list[dict[str, Any]], replacements: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for seg in segments:
        seg = dict(seg)
        seg["text"] = apply_replacements(seg.get("text", ""), replacements)
        out.append(seg)
    return out
