from __future__ import annotations

import re
from typing import Any

from rich.console import Console

console = Console()


def scan_copy_sensitive(data: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """文案二次敏感词扫描。"""
    scfg = cfg.get("sensitive_scan") or {}
    if not scfg.get("enabled", True):
        return {"ok": True, "issues": []}

    forbidden = set((cfg.get("copy") or {}).get("general", {}).get("global_forbidden_words", []))
    for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
        forbidden.update((cfg.get("copy") or {}).get(p, {}).get("forbidden_words", []))
    forbidden.update(scfg.get("extra_words", []))

    if not forbidden:
        return {"ok": True, "issues": []}

    pattern = re.compile("|".join(re.escape(w) for w in forbidden if w), re.IGNORECASE)
    issues: list[dict[str, str]] = []

    def _scan_text(path: str, text: str) -> None:
        for m in pattern.finditer(text or ""):
            issues.append({"path": path, "word": m.group(), "context": text[max(0, m.start() - 10): m.end() + 10]})

    def _walk(obj: Any, prefix: str) -> None:
        if isinstance(obj, str):
            _scan_text(prefix, obj)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _walk(v, f"{prefix}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _walk(v, f"{prefix}[{i}]")

    _walk(data, "promo")
    report = {"ok": len(issues) == 0, "issues": issues[:50], "count": len(issues)}
    if issues:
        console.print(f"[yellow]敏感词扫描[/yellow] 发现 {len(issues)} 处")
    return report
