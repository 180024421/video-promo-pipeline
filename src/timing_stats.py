from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class StepTimer:
    def __init__(self, job_dir: Path | None) -> None:
        self.job_dir = job_dir
        self._starts: dict[str, float] = {}
        self.timings: dict[str, float] = {}
        self.pipeline_started = time.time()

    def start(self, step: str) -> None:
        self._starts[step] = time.time()

    def end(self, step: str) -> None:
        if step in self._starts:
            self.timings[step] = round(time.time() - self._starts.pop(step), 2)
            self._persist()

    def finish(self) -> dict[str, Any]:
        total = round(time.time() - self.pipeline_started, 2)
        self.timings["__total__"] = total
        self._persist()
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {"step_seconds": dict(self.timings), "total_seconds": self.timings.get("__total__", 0)}

    def _persist(self) -> None:
        if not self.job_dir:
            return
        path = self.job_dir / "timing_stats.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_timing_stats(job_dir: Path) -> dict[str, Any] | None:
    p = job_dir / "timing_stats.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
