from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_loader import ROOT

AUDIT_FILE = ROOT / "logs" / "audit.log"
_MAX_LINES = 5000


def audit(event: str, detail: dict[str, Any] | None = None) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "ts": datetime.now().isoformat(),
        "event": event,
        **(detail or {}),
    }, ensure_ascii=False)
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    _trim()


def read_audit(tail: int = 200) -> list[dict[str, Any]]:
    if not AUDIT_FILE.exists():
        return []
    lines = AUDIT_FILE.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    out: list[dict[str, Any]] = []
    for ln in lines[-tail:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def _trim() -> None:
    if not AUDIT_FILE.exists():
        return
    lines = AUDIT_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > _MAX_LINES:
        AUDIT_FILE.write_text("\n".join(lines[-_MAX_LINES:]) + "\n", encoding="utf-8")
