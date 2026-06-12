from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from .config_loader import ROOT

TEAM_FILE = ROOT / "data" / "team_tokens.json"


def load_team_tokens() -> list[dict[str, Any]]:
    if not TEAM_FILE.exists():
        return []
    data = json.loads(TEAM_FILE.read_text(encoding="utf-8"))
    return data.get("tokens", []) if isinstance(data, dict) else data


def create_token(name: str, role: str = "editor") -> dict[str, Any]:
    TEAM_FILE.parent.mkdir(parents=True, exist_ok=True)
    tokens = load_team_tokens()
    token = secrets.token_urlsafe(24)
    entry = {"name": name, "role": role, "token": token}
    tokens.append(entry)
    TEAM_FILE.write_text(json.dumps({"tokens": tokens}, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def verify_team_token(token: str, cfg: dict[str, Any]) -> bool:
    tcfg = cfg.get("team") or {}
    if not tcfg.get("enabled", False):
        return True
    master = (cfg.get("web") or {}).get("auth_token", "")
    if master and token == master:
        return True
    return any(t.get("token") == token for t in load_team_tokens())
