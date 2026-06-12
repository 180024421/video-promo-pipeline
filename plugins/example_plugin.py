"""用户插件示例：复制到 plugins/ 并在 config pipeline.user_plugins 中启用。"""

from __future__ import annotations

from typing import Any


def after_pack(ctx: dict[str, Any], cfg: dict[str, Any]) -> None:
    job_dir = ctx.get("job_dir")
    if job_dir:
        print(f"[example_plugin] 任务完成: {job_dir}")
