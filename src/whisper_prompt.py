from __future__ import annotations

from typing import Any

from .terminology import load_terminology


def build_whisper_initial_prompt(cfg: dict[str, Any]) -> str:
    """合并 initial_prompt、hotwords、术语表，提升专有名词识别率。"""
    wcfg = cfg.get("whisper") or {}
    parts: list[str] = []
    initial = (wcfg.get("initial_prompt") or "").strip()
    if initial:
        parts.append(initial)
    hotwords = wcfg.get("hotwords") or []
    if isinstance(hotwords, str):
        hotwords = [x.strip() for x in hotwords.split(",") if x.strip()]
    parts.extend(str(x).strip() for x in hotwords if str(x).strip())
    if wcfg.get("hotwords_from_terminology", True):
        reps = load_terminology(cfg)
        parts.extend(str(k).strip() for k in reps.keys() if str(k).strip())
    # 去重保序
    seen: set[str] = set()
    unique: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    text = "，".join(unique)
    return text[:896]
