from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .config_loader import ROOT
from .rag_copy import KNOWLEDGE_DIR, _chunk_text

INDEX_FILE = ROOT / "knowledge" / ".embed_index.json"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1
    nb = math.sqrt(sum(x * x for x in b)) or 1
    return dot / (na * nb)


def _embed_texts(texts: list[str], cfg: dict[str, Any]) -> list[list[float]]:
    rcfg = cfg.get("rag") or {}
    backend = rcfg.get("embed_backend", "auto")
    if backend in ("sentence_transformers", "auto"):
        try:
            from sentence_transformers import SentenceTransformer
            model_name = rcfg.get("embed_model", "paraphrase-multilingual-MiniLM-L12-v2")
            model = SentenceTransformer(model_name)
            return model.encode(texts, show_progress_bar=False).tolist()
        except Exception:
            if backend == "sentence_transformers":
                raise
    # 回退：简单词袋向量
    return [_bag_vector(t) for t in texts]


def _bag_vector(text: str, dim: int = 128) -> list[float]:
    vec = [0.0] * dim
    for tok in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", text.lower()):
        vec[hash(tok) % dim] += 1.0
    return vec


def build_index(cfg: dict[str, Any]) -> int:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for p in KNOWLEDGE_DIR.glob("*"):
        if not p.is_file() or p.name.startswith("."):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for i, chunk in enumerate(_chunk_text(text, int((cfg.get("rag") or {}).get("chunk_size", 500)))):
            entries.append({"file": p.name, "chunk_id": i, "text": chunk})
    if not entries:
        INDEX_FILE.write_text("[]", encoding="utf-8")
        return 0
    vecs = _embed_texts([e["text"] for e in entries], cfg)
    for e, v in zip(entries, vecs):
        e["vector"] = v
    INDEX_FILE.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return len(entries)


def retrieve_context_vector(query: str, cfg: dict[str, Any], top_k: int = 3) -> str:
    rcfg = cfg.get("rag") or {}
    if not rcfg.get("enabled", False):
        return ""
    if rcfg.get("use_vectors", True):
        if not INDEX_FILE.exists() or rcfg.get("rebuild_index_on_query", False):
            build_index(cfg)
        if INDEX_FILE.exists():
            entries = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            if entries:
                qv = _embed_texts([query], cfg)[0]
                scored = sorted(
                    (( _cosine(qv, e["vector"]), e["text"]) for e in entries if "vector" in e),
                    key=lambda x: -x[0],
                )
                parts = [t for _, t in scored[:top_k] if _ > 0.05]
                if parts:
                    return "\n\n---\n\n".join(parts)
    from .rag_copy import retrieve_context
    return retrieve_context(query, cfg, top_k=top_k)
