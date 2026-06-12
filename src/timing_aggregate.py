from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .timing_stats import load_timing_stats


def aggregate_job_timings(output_dir: Path, limit: int = 50) -> dict[str, Any]:
    """汇总各任务步骤耗时，用于仪表盘。"""
    per_job: list[dict[str, Any]] = []
    step_totals: dict[str, list[float]] = {}

    if not output_dir.exists():
        return {"jobs": [], "step_averages": {}, "bottleneck": None}

    dirs = sorted(
        [d for d in output_dir.iterdir() if d.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]

    for d in dirs:
        stats = load_timing_stats(d)
        if not stats:
            continue
        steps = stats.get("step_seconds") or stats.get("steps") or {}
        total = float(stats.get("total_seconds") or steps.get("__total__") or 0)
        per_job.append({"job": d.name, "total_seconds": total, "steps": steps})
        for name, sec in steps.items():
            if name.startswith("__"):
                continue
            step_totals.setdefault(name, []).append(float(sec))

    averages = {k: round(sum(v) / len(v), 2) for k, v in step_totals.items() if v}
    bottleneck = max(averages.items(), key=lambda x: x[1])[0] if averages else None
    return {
        "jobs": per_job,
        "step_averages": averages,
        "bottleneck": bottleneck,
        "job_count": len(per_job),
    }
