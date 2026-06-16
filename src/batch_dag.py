"""批量任务编排 DAG。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config_loader import ROOT


@dataclass
class BatchNode:
  video: str
  job_name: str = ""
  priority: int = 0
  depends_on: list[str] = field(default_factory=list)
  status: str = "pending"
  preset: str = ""


def load_batch_plan(path: Path | None = None) -> list[BatchNode]:
  p = path or ROOT / "data" / "batch_plan.json"
  if not p.exists():
    return []
  raw = json.loads(p.read_text(encoding="utf-8"))
  return [BatchNode(**item) for item in raw.get("nodes", [])]


def save_batch_plan(nodes: list[BatchNode], path: Path | None = None) -> Path:
  p = path or ROOT / "data" / "batch_plan.json"
  p.parent.mkdir(parents=True, exist_ok=True)
  data = {"nodes": [{"video": n.video, "job_name": n.job_name, "priority": n.priority,
                     "depends_on": n.depends_on, "status": n.status, "preset": n.preset} for n in nodes]}
  p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
  return p


def next_runnable(nodes: list[BatchNode]) -> BatchNode | None:
  """返回下一个可执行任务（依赖已完成）。"""
  done = {n.job_name for n in nodes if n.status == "done" and n.job_name}
  pending = [n for n in nodes if n.status == "pending"]
  pending.sort(key=lambda x: -x.priority)
  for n in pending:
    if all(dep in done for dep in n.depends_on):
      return n
  return None


def batch_plan_from_watch(watch_dir: Path, *, preset: str = "") -> list[BatchNode]:
  nodes: list[BatchNode] = []
  for i, p in enumerate(sorted(watch_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime)):
    nodes.append(BatchNode(video=str(p), priority=len(watch_dir.glob("*.mp4")) - i, preset=preset))
  return nodes
