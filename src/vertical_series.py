"""自动竖屏系列化：一次长视频 → N 条竖屏各配文案。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .copywriter import generate_copy


def plan_vertical_series(
  segments: list[dict[str, Any]],
  cfg: dict[str, Any],
  *,
  count: int | None = None,
) -> list[dict[str, Any]]:
  """根据分段规划 N 个竖屏切片时间点。"""
  vcfg = cfg.get("clip_short") or {}
  n = count or int(vcfg.get("multi_clip_count", 3))
  if not segments:
    return []
  total = segments[-1]["end"] - segments[0]["start"]
  chunk = total / max(n, 1)
  plans: list[dict[str, Any]] = []
  for i in range(n):
    start = segments[0]["start"] + i * chunk
    end = min(start + chunk, segments[-1]["end"])
    plans.append({
      "index": i + 1,
      "start_sec": round(start, 2),
      "end_sec": round(end, 2),
      "hook": segments[int(i * len(segments) / max(n, 1))]["text"][:40] if segments else "",
    })
  return plans


def export_series_pack(
  job_dir: Path,
  work_video: Path,
  transcript: str,
  segments: list[dict[str, Any]],
  cfg: dict[str, Any],
) -> dict[str, Any]:
  """生成系列化规划 + 各集独立文案（竖屏切片由流水线 clip_short 步骤执行）。"""
  plans = plan_vertical_series(segments, cfg)
  series_dir = job_dir / "series"
  series_dir.mkdir(exist_ok=True)
  items: list[dict[str, Any]] = []
  for plan in plans:
    idx = plan["index"]
    excerpt = transcript[:2000]
    copy = generate_copy(excerpt, cfg, series_dir / f"ep{idx}")
    items.append({"index": idx, "plan": plan, "source_video": str(work_video), "copy": copy})
  out = {"episodes": items, "count": len(items)}
  (job_dir / "series_plan.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
  return out
