from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .config_loader import ROOT
from .bilibili_upload import get_access_token

OAUTH_AUTHORIZE = "https://account.bilibili.com/pc/account-pc/auth/oauth"
TOKEN_FILE = ROOT / "data" / "bilibili_oauth.json"


def build_authorize_url(client_id: str, redirect_uri: str, state: str = "vpp") -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{OAUTH_AUTHORIZE}?{urllib.parse.urlencode(params)}"


def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict[str, Any]:
    url = "https://open.bilibili.com/oauth2/access_token"
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def save_tokens(data: dict[str, Any]) -> Path:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return TOKEN_FILE


def load_tokens() -> dict[str, Any] | None:
    if not TOKEN_FILE.exists():
        return None
    return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))


def refresh_stored_tokens(cfg: dict[str, Any]) -> dict[str, Any]:
    pcfg = (cfg.get("publish") or {}).get("bilibili") or {}
    stored = load_tokens() or {}
    refresh = stored.get("refresh_token") or pcfg.get("refresh_token", "")
    client_id = pcfg.get("client_id", "")
    client_secret = pcfg.get("client_secret", "")
    if not refresh:
        return {"ok": False, "error": "无 refresh_token，请先 OAuth 授权"}
    data = get_access_token(client_id, client_secret, refresh)
    save_tokens(data)
    return {"ok": True, **data}
