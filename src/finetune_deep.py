"""lmstudio-finetune 深度联动增强。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config_loader import ROOT


def bridge_path() -> Path:
    return ROOT / "data" / "finetune_bridge.json"


def load_finetune_feedback() -> list[dict[str, Any]]:
    """加载微调反馈数据。"""
    path = ROOT / "data" / "finetune_feedback.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def export_feedback_for_training(out_path: Path, *, min_score: float = 0.6) -> dict[str, Any]:
    """将高评分文案导出为训练数据格式。"""
    feedback = load_finetune_feedback()
    train_rows: list[dict[str, Any]] = []
    for fb in feedback:
        score = float(fb.get("score", 0))
        if score < min_score:
            continue
        instruction = fb.get("instruction", "")
        output = fb.get("output", "")
        if not instruction or not output:
            continue
        train_rows.append({
            "instruction": instruction,
            "input": fb.get("input", ""),
            "output": output,
            "_from_feedback": True,
            "_score": score,
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in train_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"count": len(train_rows), "out": str(out_path)}


def check_bridge_ready() -> dict[str, Any]:
    """检查微调联动状态。"""
    bp = bridge_path()
    bridge_ok = bp.exists()
    model = ""
    if bridge_ok:
        data = json.loads(bp.read_text(encoding="utf-8"))
        model = data.get("recommended_lm_studio_model", "")
    fb = load_finetune_feedback()
    return {
        "bridge_exists": bridge_ok,
        "recommended_model": model,
        "feedback_count": len(fb),
        "ready_to_finetune": len(fb) >= 5,
    }
