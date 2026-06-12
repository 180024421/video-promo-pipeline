from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config_loader import ROOT

KNOWLEDGE_DIR = ROOT / "knowledge"


def list_documents() -> list[dict[str, str]]:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, str]] = []
    for p in sorted(KNOWLEDGE_DIR.glob("*")):
        if p.is_file() and p.suffix.lower() in {".txt", ".md", ".json"}:
            items.append({"name": p.name, "path": str(p), "size": str(p.stat().st_size)})
    return items


def save_document(filename: str, content: str) -> Path:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.\-]", "_", filename) or "doc.txt"
    path = KNOWLEDGE_DIR / safe
    path.write_text(content, encoding="utf-8")
    return path


def _chunk_text(text: str, size: int = 500) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) < size:
            buf = f"{buf}\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    return chunks or [text[:size]]


def retrieve_context(query: str, cfg: dict[str, Any], top_k: int = 3) -> str:
    """简单关键词检索，将相关知识片段注入文案 prompt。"""
    rcfg = cfg.get("rag") or {}
    if not rcfg.get("enabled", False):
        return ""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    keywords = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", query))
    if not keywords:
        return ""
    scored: list[tuple[int, str]] = []
    for p in KNOWLEDGE_DIR.glob("*"):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for chunk in _chunk_text(text, int(rcfg.get("chunk_size", 500))):
            score = sum(1 for kw in keywords if kw.lower() in chunk.lower())
            if score:
                scored.append((score, chunk))
    scored.sort(key=lambda x: -x[0])
    parts = [c for _, c in scored[:top_k]]
    return "\n\n---\n\n".join(parts)
