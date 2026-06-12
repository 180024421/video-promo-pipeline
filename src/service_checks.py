from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .config_loader import load_config


def check_gpt_sovits(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    gcfg = (cfg.get("dubbing") or {}).get("gpt_sovits") or {}
    base = gcfg.get("base_url", "http://127.0.0.1:9880").rstrip("/")
    result = {"ok": False, "base_url": base, "message": ""}
    for path in ("/", "/docs", "/tts"):
        try:
            with urllib.request.urlopen(f"{base}{path}", timeout=2) as resp:
                if resp.status < 500:
                    result["ok"] = True
                    result["message"] = "服务可达"
                    return result
        except urllib.error.HTTPError as e:
            if e.code < 500:
                result["ok"] = True
                result["message"] = f"HTTP {e.code}"
                return result
        except Exception as e:
            result["message"] = str(e)
    return result


def check_lm_studio_detail(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    lcfg = cfg.get("lm_studio") or {}
    if not lcfg.get("enabled", True):
        return {"ok": True, "skipped": True}
    base = lcfg.get("base_url", "http://127.0.0.1:1234/v1").rstrip("/").removesuffix("/v1")
    url = f"{base}/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("id", "") for m in data.get("data", [])]
            return {"ok": True, "models": models, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}
