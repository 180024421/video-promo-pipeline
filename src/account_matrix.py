from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config_loader import ROOT

MATRIX_FILE = ROOT / "data" / "account_matrix.json"


def load_accounts() -> list[dict[str, Any]]:
    if not MATRIX_FILE.exists():
        return []
    data = json.loads(MATRIX_FILE.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("accounts", [])


def save_accounts(accounts: list[dict[str, Any]]) -> Path:
    MATRIX_FILE.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_FILE.write_text(json.dumps({"accounts": accounts}, ensure_ascii=False, indent=2), encoding="utf-8")
    return MATRIX_FILE


def apply_account_variant(copy_data: dict[str, Any], account: dict[str, Any]) -> dict[str, Any]:
    """为矩阵账号生成标题/封面变体元数据。"""
    platform = account.get("platform", "bilibili")
    variant = {
        "account_id": account.get("id", ""),
        "account_name": account.get("name", ""),
        "platform": platform,
        "title_suffix": account.get("title_suffix", ""),
        "persona": account.get("persona", ""),
    }
    plat = copy_data.get(platform) or {}
    if variant["title_suffix"] and plat.get("recommended_title"):
        variant["title"] = plat["recommended_title"] + variant["title_suffix"]
    elif plat.get("recommended_title"):
        variant["title"] = plat["recommended_title"]
    return variant
