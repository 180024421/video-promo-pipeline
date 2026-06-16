"""成片对比播放器：列出任务内各版本视频。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


VARIANT_TAGS = [
  ("raw", "_raw", "原片备份"),
  ("cut", "_cut", "粗剪"),
  ("smart", "_smart", "智能剪"),
  ("broll", "_broll", "B-roll"),
  ("dubbed", "_dubbed", "配音版"),
  ("subtitled", "_subtitled", "硬字幕"),
  ("enhanced", "_enhanced", "音频增强"),
  ("short", "_short_", "竖屏"),
]


def list_video_variants(job_dir: Path) -> list[dict[str, Any]]:
  variants: list[dict[str, Any]] = []
  seen: set[str] = set()
  for p in sorted(job_dir.rglob("*")):
    if not p.is_file() or p.suffix.lower() not in {".mp4", ".mkv", ".mov", ".webm"}:
      continue
    rel = p.relative_to(job_dir).as_posix()
    if rel in seen:
      continue
    seen.add(rel)
    label = p.stem
    for _id, tag, name in VARIANT_TAGS:
      if tag in p.stem:
        label = name
        break
    variants.append({
      "id": p.stem,
      "label": label,
      "path": rel,
      "name": p.name,
      "size": p.stat().st_size,
    })
  variants.sort(key=lambda x: x["name"])
  return variants
