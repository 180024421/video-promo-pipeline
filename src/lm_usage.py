from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_loader import ROOT

_lock = threading.Lock()
_stats: dict[str, Any] = {"total_calls": 0, "total_prompt_tokens": 0, "total_completion_tokens": 0, "calls": []}
_LOG = ROOT / "logs" / "lm_usage.json"


def record_usage(
    *,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    label: str = "chat",
    duration_ms: int = 0,
) -> None:
    entry = {
        "at": datetime.now().isoformat(),
        "model": model,
        "label": label,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "duration_ms": duration_ms,
    }
    with _lock:
        _stats["total_calls"] += 1
        _stats["total_prompt_tokens"] += prompt_tokens
        _stats["total_completion_tokens"] += completion_tokens
        _stats["calls"].append(entry)
        if len(_stats["calls"]) > 500:
            _stats["calls"] = _stats["calls"][-500:]
        _persist()


def record_from_response(resp: Any, label: str = "chat", duration_ms: int = 0) -> None:
    usage = getattr(resp, "usage", None)
    model = getattr(resp, "model", "") or ""
    if usage:
        record_usage(
            model=str(model),
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            label=label,
            duration_ms=duration_ms,
        )
    else:
        record_usage(model=str(model), label=label, duration_ms=duration_ms)


def _persist() -> None:
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    _LOG.write_text(json.dumps(_stats, ensure_ascii=False, indent=2), encoding="utf-8")


def load_stats() -> dict[str, Any]:
    if _LOG.exists():
        try:
            return json.loads(_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    with _lock:
        return dict(_stats)


def estimate_cost(stats: dict[str, Any] | None = None) -> dict[str, Any]:
    s = stats or load_stats()
    total = int(s.get("total_prompt_tokens", 0)) + int(s.get("total_completion_tokens", 0))
    # 本地 LM Studio 免费；估算按 $0 或用户自定义
    return {"total_tokens": total, "estimated_usd": 0.0, "note": "本地 LM Studio 通常不计费"}
