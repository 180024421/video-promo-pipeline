"""内置插件示例：可在 config.yaml pipeline.plugins 中引用。"""

from __future__ import annotations

from typing import Any


def log_job_summary(ctx: dict[str, Any], cfg: dict[str, Any]) -> None:
    job_dir = ctx.get("job_dir")
    if job_dir:
        print(f"[plugin] 任务完成: {job_dir}")
