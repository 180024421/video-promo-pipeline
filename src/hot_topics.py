from __future__ import annotations

import json
import urllib.request
from typing import Any

from rich.console import Console

console = Console()

DEFAULT_TOPICS = {
    "bilibili": ["程序员", "Java", "Spring Boot", "项目实战", "技术分享"],
    "xiaohongshu": ["程序员副业", "干货分享", "职场成长", "效率工具"],
}

BILI_RANK_URL = "https://api.bilibili.com/x/web-interface/ranking/v2?rid=36&type=all"


def fetch_bilibili_hot(limit: int = 10) -> list[str]:
    try:
        req = urllib.request.Request(BILI_RANK_URL, headers={"User-Agent": "video-promo-pipeline/3.5"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        items = (data.get("data") or {}).get("list") or []
        tags: list[str] = []
        for it in items[:limit]:
            title = (it.get("title") or "").strip()
            if title and len(title) <= 20:
                tags.append(title)
        return tags
    except Exception as e:
        console.print(f"[dim]B站热榜获取失败: {e}[/dim]")
        return []


def fetch_lm_topics(transcript: str, cfg: dict[str, Any], limit: int = 5) -> list[str]:
    if not transcript.strip():
        return []
    lcfg = cfg.get("lm_studio") or {}
    if not lcfg.get("enabled", True):
        return []
    try:
        from .lm_client import call_lm, make_lm_client, parse_json_content

        prompt = (
            f"根据以下视频转写摘要，提取 {limit} 个适合 B站/小红书 的话题标签（不带#）。"
            f"输出 JSON: {{\"topics\":[\"标签1\"]}}\n\n{transcript[:3000]}"
        )
        client = make_lm_client(cfg)
        content = call_lm(client, prompt, cfg, "你是短视频运营，输出 JSON。")
        data = parse_json_content(content)
        if isinstance(data, dict):
            return [str(t) for t in (data.get("topics") or [])[:limit]]
    except Exception as e:
        console.print(f"[dim]LM 热点生成失败: {e}[/dim]")
    return []


def inject_hot_topics(cfg: dict[str, Any], transcript: str = "") -> list[str]:
    hcfg = cfg.get("hot_topics") or {}
    if not hcfg.get("enabled", False):
        return []

    custom = list(hcfg.get("custom", []))
    platform = hcfg.get("platform", "bilibili")
    defaults = list(hcfg.get("defaults", DEFAULT_TOPICS.get(platform, [])))
    max_n = int(hcfg.get("max_inject", 3))
    source = hcfg.get("source", "auto")

    pool: list[str] = list(custom)
    if source in ("auto", "bilibili_api", "api"):
        pool.extend(fetch_bilibili_hot(limit=10))
    if source in ("auto", "lm") and transcript:
        pool.extend(fetch_lm_topics(transcript, cfg, limit=max_n))
    pool.extend(defaults)

    out: list[str] = []
    for t in pool:
        tag = t if str(t).startswith("#") else f"#{t}"
        if tag not in out:
            out.append(tag)
        if len(out) >= max_n:
            break
    return out
