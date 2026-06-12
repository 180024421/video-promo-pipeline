from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def export_english_pack(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """一键英文轨：翻译简介 + 导出英文字幕说明。"""
    icfg = cfg.get("i18n_workflow") or {}
    if not icfg.get("enabled", False):
        return {"skipped": True}

    from .i18n import translate_narration

    result: dict[str, Any] = {"files": []}
    segments_path = job_dir / "segments.json"
    if segments_path.exists():
        seg_data = json.loads(segments_path.read_text(encoding="utf-8"))
        segments = seg_data.get("segments", [])
        narr = {"segments": segments}
        en = translate_narration(narr, {**cfg, "i18n": {**(cfg.get("i18n") or {}), "target_lang": "en"}}, job_dir)
        en_path = job_dir / "narration_en.json"
        en_path.write_text(json.dumps(en, ensure_ascii=False, indent=2), encoding="utf-8")
        result["files"].append(str(en_path))

    promo_path = job_dir / "promo_copy.json"
    if promo_path.exists() and icfg.get("translate_description", True):
        from .copywriter import generate_copy
        transcript = (job_dir / "transcript.txt").read_text(encoding="utf-8") if (job_dir / "transcript.txt").exists() else ""
        en_cfg = dict(cfg)
        copy = dict(en_cfg.get("copy") or {})
        for p in ("bilibili", "youtube"):
            if p in copy:
                copy[p] = {**copy[p], "language": "en"}
        en_cfg["copy"] = copy
        # 简化：写英文占位 manifest
        en_desc = job_dir / "description_en.txt"
        en_desc.write_text(f"English description for: {job_dir.name}\n\n{transcript[:2000]}", encoding="utf-8")
        result["files"].append(str(en_desc))

    out = job_dir / "i18n_english_pack.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]英文包[/green] {out}")
    return result
