#!/usr/bin/env python3
"""Redis Worker：消费分布式任务队列。"""

from __future__ import annotations

from pathlib import Path

from src.config_loader import load_config
from src.pipeline import run_pipeline
from src.redis_queue import start_redis_worker


def main() -> None:
    cfg = load_config()

    def handler(spec: dict) -> None:
        run_pipeline(
            Path(spec.get("video_path") or spec["job_dir"]),
            job_dir=Path(spec["job_dir"]) if spec.get("job_dir") else None,
            skip_cut=spec.get("skip_cut", False),
            skip_burn=spec.get("skip_burn", False),
            skip_copy=spec.get("skip_copy", False),
            skip_dub=spec.get("skip_dub", False),
            only_transcribe=spec.get("only_transcribe", False),
            preset=spec.get("preset"),
            cfg_override=spec.get("cfg_override"),
        )

    start_redis_worker(handler, cfg)
    import time
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
