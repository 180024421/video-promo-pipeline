from __future__ import annotations

import json
import multiprocessing
import sys
import tempfile
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

_processes: dict[str, multiprocessing.Process] = {}


def _pipeline_worker(spec_path: str) -> None:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    from .pipeline import run_pipeline

    video = spec.get("video_path")
    run_pipeline(
        Path(video) if video else Path(spec["job_dir"]),
        skip_cut=spec.get("skip_cut", False),
        skip_burn=spec.get("skip_burn", False),
        skip_copy=spec.get("skip_copy", False),
        skip_dub=spec.get("skip_dub", False),
        only_transcribe=spec.get("only_transcribe", False),
        only_copy=spec.get("only_copy", False),
        only_dub=spec.get("only_dub", False),
        only_burn=spec.get("only_burn", False),
        only_short=spec.get("only_short", False),
        only_pack=spec.get("only_pack", False),
        job_dir=Path(spec["job_dir"]) if spec.get("job_dir") else None,
        force=spec.get("force", False),
        from_step=spec.get("from_step"),
        preset=spec.get("preset"),
        cfg_override=spec.get("cfg_override"),
    )


def start_pipeline_subprocess(job_name: str, spec: dict[str, Any]) -> multiprocessing.Process:
    """在独立进程中运行流水线，支持 terminate/kill 强制中断。"""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="job_spec_")
    import os
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
    proc = multiprocessing.Process(target=_pipeline_worker, args=(path,), name=f"pipeline-{job_name}")
    proc.start()
    _processes[job_name] = proc
    return proc


def terminate_pipeline(job_name: str) -> bool:
    proc = _processes.get(job_name)
    if not proc:
        return False
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=8)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=3)
    _processes.pop(job_name, None)
    return True


def is_running(job_name: str) -> bool:
    proc = _processes.get(job_name)
    return bool(proc and proc.is_alive())
