from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

_TECH_PATTERN = re.compile(r"\b[A-Z]{2,}[a-zA-Z0-9]*\b|[A-Za-z]+[0-9]+|[\u4e00-\u9fff]{2,6}(?:框架|引擎|系统|平台)")


def suggest_terminology(transcript: str, cfg: dict[str, Any], out_dir: Path | None = None) -> list[dict[str, str]]:
    tcfg = cfg.get("terminology") or {}
    if not tcfg.get("suggest_enabled", True):
        return []

    found = _TECH_PATTERN.findall(transcript or "")
    counts = Counter(w for w in found if len(w) >= 2)
    existing = set()
    try:
        from .terminology import load_terminology
        reps = load_terminology(cfg)
        existing = set(reps.keys()) | set(reps.values())
    except Exception:
        pass

    suggestions: list[dict[str, str]] = []
    for word, n in counts.most_common(30):
        if word in existing:
            continue
        suggestions.append({"term": word, "count": str(n), "suggested_fix": word})

    if out_dir:
        (out_dir / "terminology_suggestions.json").write_text(
            json.dumps(suggestions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if suggestions:
        console.print(f"[cyan]术语建议[/cyan] {len(suggestions)} 条")
    return suggestions
