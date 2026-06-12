from __future__ import annotations

from typing import Any

from rich.console import Console

console = Console()

DEFAULT_TOPICS = {
    "bilibili": ["程序员", "Java", "Spring Boot", "项目实战", "技术分享"],
    "xiaohongshu": ["程序员副业", "干货分享", "职场成长", "效率工具"],
}


def inject_hot_topics(cfg: dict[str, Any]) -> list[str]:
    """返回要注入的热点话题（配置 + 内置默认）。"""
    hcfg = cfg.get("hot_topics") or {}
    if not hcfg.get("enabled", False):
        return []
    custom = list(hcfg.get("custom", []))
    platform = hcfg.get("platform", "bilibili")
    defaults = list(hcfg.get("defaults", DEFAULT_TOPICS.get(platform, [])))
    max_n = int(hcfg.get("max_inject", 3))
    out: list[str] = []
    for t in custom + defaults:
        tag = t if t.startswith("#") else f"#{t}"
        if tag not in out:
            out.append(tag)
        if len(out) >= max_n:
            break
    return out
