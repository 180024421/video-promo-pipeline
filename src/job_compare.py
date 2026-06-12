from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .timing_stats import load_timing_stats


def compare_jobs(job_a: Path, job_b: Path) -> dict[str, Any]:
    def _load(job: Path) -> dict[str, Any]:
        s = {}
        if (job / "summary.json").exists():
            s = json.loads((job / "summary.json").read_text(encoding="utf-8"))
        timing = load_timing_stats(job) or {}
        promo = {}
        if (job / "promo_copy.json").exists():
            promo = json.loads((job / "promo_copy.json").read_text(encoding="utf-8"))
        return {"name": job.name, "summary": s, "timing": timing, "promo": promo}

    a, b = _load(job_a), _load(job_b)
    ta = (a["timing"].get("step_seconds") or {})
    tb = (b["timing"].get("step_seconds") or {})
    steps = sorted(set(ta) | set(tb))
    timing_diff = [
        {"step": s, "a": ta.get(s, 0), "b": tb.get(s, 0), "delta": round((tb.get(s, 0) or 0) - (ta.get(s, 0) or 0), 2)}
        for s in steps if not s.startswith("__")
    ]
    title_a = ((a["promo"].get("bilibili") or {}).get("recommended_title") or "")
    title_b = ((b["promo"].get("bilibili") or {}).get("recommended_title") or "")
    return {
        "job_a": a["name"],
        "job_b": b["name"],
        "timing_diff": timing_diff,
        "total_a": a["timing"].get("total_seconds", 0),
        "total_b": b["timing"].get("total_seconds", 0),
        "title_a": title_a,
        "title_b": title_b,
        "titles_differ": title_a != title_b,
    }
