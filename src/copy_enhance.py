from __future__ import annotations

import difflib
import re
from typing import Any

from rich.console import Console

console = Console()


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def deduplicate_titles(titles: list[str], threshold: float = 0.82) -> list[str]:
    out: list[str] = []
    for t in titles:
        t = t.strip()
        if not t:
            continue
        if any(_similar(t, x) >= threshold for x in out):
            continue
        out.append(t)
    return out


def consistency_check_title(title: str, transcript: str, keywords: list[str] | None = None) -> dict[str, Any]:
    """轻量一致性：标题关键词是否出现在转写中。"""
    transcript_l = transcript.lower()
    title_l = title.lower()
    kw = keywords or []
    hits = [k for k in kw if k.lower() in title_l and k.lower() in transcript_l]
    title_tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", title)
    content_hits = sum(1 for tok in title_tokens if tok.lower() in transcript_l)
    score = min(1.0, (content_hits / max(len(title_tokens), 1)) * 0.7 + (len(hits) / max(len(kw), 1)) * 0.3)
    ok = score >= 0.35 or len(title_tokens) <= 3
    return {"title": title, "score": round(score, 3), "ok": ok, "keyword_hits": hits}


def score_titles(titles: list[str], transcript: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    gen = (cfg.get("copy") or {}).get("general", {})
    if not gen.get("title_scoring_enabled", True):
        return [{"title": t, "score": 0.5, "ok": True} for t in titles]
    kw: list[str] = []
    for p in ("bilibili", "xiaohongshu", "douyin"):
        kw.extend((cfg.get("copy") or {}).get(p, {}).get("keywords") or [])
    ranked = []
    for t in titles:
        r = consistency_check_title(t, transcript, kw)
        ranked.append(r)
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


def post_process_copy(data: dict[str, Any], cfg: dict[str, Any], transcript: str) -> dict[str, Any]:
    gen = (cfg.get("copy") or {}).get("general", {})
    if gen.get("deduplicate_titles", True) and isinstance(data.get("bilibili"), dict):
        b = data["bilibili"]
        if b.get("titles"):
            b["titles"] = deduplicate_titles(list(b["titles"]))
            if gen.get("title_scoring_enabled", True):
                b["title_scores"] = score_titles(b["titles"], transcript, cfg)
                if b["title_scores"]:
                    b["recommended_title"] = b["title_scores"][0]["title"]
    if gen.get("consistency_check", True) and isinstance(data.get("bilibili"), dict):
        b = data["bilibili"]
        titles = b.get("titles") or []
        if titles and not b.get("title_scores"):
            b["title_scores"] = score_titles(titles, transcript, cfg)
        failed = [x for x in (b.get("title_scores") or []) if not x.get("ok")]
        if failed:
            console.print(f"[yellow]标题一致性警告[/yellow] {len(failed)} 个标题与内容匹配度偏低")
            b["consistency_warnings"] = failed[:5]
    hot = gen.get("custom_hot_topics") or []
    if hot and isinstance(data.get("xiaohongshu"), dict):
        x = data["xiaohongshu"]
        topics = list(x.get("topics") or [])
        for h in hot[:3]:
            tag = h if h.startswith("#") else f"#{h}"
            if tag not in topics:
                topics.append(tag)
        x["topics"] = topics[: int((cfg.get("copy") or {}).get("xiaohongshu", {}).get("max_topics", 10))]
    return data
