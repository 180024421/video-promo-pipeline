from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

StepCallback = Callable[[str], None] | None

PIPELINE_STEPS = [
    "备份原片", "粗剪", "转写", "智能剪辑", "视觉分析", "B-roll",
    "配音解说", "多语言", "烧录字幕", "竖屏切片", "推广文案", "封面", "打包导出", "发布",
]


class ProgressTracker:
    def __init__(self, job_dir: Path | None, on_step: StepCallback = None) -> None:
        self.job_dir = job_dir
        self.on_step = on_step
        self.current = ""
        self.completed: list[str] = []
        self.skipped: list[str] = []

    def tick(self, step: str) -> None:
        if self.current and self.current not in self.completed:
            self.completed.append(self.current)
        self.current = step
        if self.on_step:
            self.on_step(step)
        self._persist()

    def skip(self, step: str) -> None:
        self.skipped.append(step)
        self._persist()

    def done(self) -> None:
        if self.current and self.current not in self.completed:
            self.completed.append(self.current)
        self.current = "完成"
        if self.on_step:
            self.on_step("完成")
        self._persist()

    def progress_pct(self) -> int:
        if self.current == "完成":
            return 100
        try:
            idx = PIPELINE_STEPS.index(self.current)
        except ValueError:
            return 0
        return int((idx + 1) / len(PIPELINE_STEPS) * 100)

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": PIPELINE_STEPS,
            "current": self.current,
            "completed": self.completed,
            "skipped": self.skipped,
            "progress": self.progress_pct(),
            "updated_at": datetime.now().isoformat(),
        }

    def _persist(self) -> None:
        if not self.job_dir:
            return
        path = self.job_dir / "pipeline_progress.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_progress(job_dir: Path) -> dict[str, Any] | None:
    path = job_dir / "pipeline_progress.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
