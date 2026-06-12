from __future__ import annotations

import urllib.request
from typing import Any


def lm_studio_reachable(cfg: dict[str, Any]) -> bool:
    lcfg = cfg.get("lm_studio") or {}
    if not lcfg.get("enabled", True):
        return False
    base = lcfg.get("base_url", "http://127.0.0.1:1234/v1")
    url = base.rstrip("/").removesuffix("/v1") + "/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def apply_offline_fallback(cfg: dict[str, Any]) -> dict[str, Any]:
    """无 LM Studio 时自动降级：跳过文案/智能剪辑/配音。"""
    ocfg = cfg.get("offline") or {}
    if not ocfg.get("auto_fallback", True):
        return cfg
    if lm_studio_reachable(cfg):
        return cfg
    out = dict(cfg)
    out.setdefault("pipeline", {})
    out["pipeline"] = {**out.get("pipeline", {}), "_offline": True}
    if ocfg.get("skip_copy_when_offline", True):
        out.setdefault("lm_studio", {})["enabled"] = False
    sc = dict(out.get("smart_cut") or {})
    sc["enabled"] = False
    out["smart_cut"] = sc
    nc = dict(out.get("narration") or {})
    if ocfg.get("skip_dub_when_offline", True):
        nc["enabled"] = False
    out["narration"] = nc
    return out
