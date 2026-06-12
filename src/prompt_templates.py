from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config_loader import ROOT

TEMPLATES_DIR = ROOT / "templates" / "prompts"


def list_templates() -> list[dict[str, str]]:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, str]] = []
    for p in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            items.append({"id": p.stem, "name": data.get("name", p.stem), "platform": data.get("platform", "")})
        except Exception:
            items.append({"id": p.stem, "name": p.stem, "platform": ""})
    return items


def get_template(template_id: str) -> dict[str, Any] | None:
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_template(template_id: str, data: dict[str, Any]) -> Path:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMPLATES_DIR / f"{template_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def apply_template_to_cfg(cfg: dict[str, Any], template_id: str) -> dict[str, Any]:
    tpl = get_template(template_id)
    if not tpl:
        return cfg
    platform = tpl.get("platform", "bilibili")
    copy = dict(cfg.get("copy") or {})
    plat = dict(copy.get(platform) or {})
    if tpl.get("persona"):
        plat["persona"] = tpl["persona"]
    if tpl.get("style"):
        plat["style"] = tpl["style"]
    if tpl.get("prompt_override"):
        plat["prompt_override"] = tpl["prompt_override"]
    if tpl.get("system_prompt"):
        lm = dict(cfg.get("lm_studio") or {})
        lm["system_prompt"] = tpl["system_prompt"]
        cfg = {**cfg, "lm_studio": lm}
    copy[platform] = plat
    return {**cfg, "copy": copy}
