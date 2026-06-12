from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from .auto_cut import run_auto_editor
from .config_loader import load_config, output_dir
from .copywriter import generate_copy
from .subtitle_burn import burn_subtitles
from .transcribe import transcribe_video

console = Console()


def run_pipeline(
    video_path: Path,
    *,
    skip_cut: bool = False,
    skip_burn: bool = False,
    skip_copy: bool = False,
    config_path: Path | None = None,
) -> dict[str, Any]:
    video_path = video_path.resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"视频不存在: {video_path}")

    cfg = load_config(config_path)
    job_name = f"{video_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir = output_dir(cfg, job_name)

    # 备份原片
    raw_copy = out_dir / video_path.name
    if not raw_copy.exists():
        shutil.copy2(video_path, raw_copy)

    console.print(f"[bold]任务目录[/bold] {out_dir}")

    # 1. 可选粗剪
    work_video = raw_copy
    if not skip_cut:
        cut = run_auto_editor(raw_copy, cfg, out_dir)
        if cut is not None:
            work_video = cut

    # 2. 字幕转写
    tx = transcribe_video(work_video, cfg, out_dir)

    # 3. 烧录字幕
    final_video = work_video
    if not skip_burn:
        try:
            final_video = burn_subtitles(work_video, tx["srt_path"], cfg, out_dir)
        except RuntimeError as e:
            console.print(f"[yellow]{e}[/yellow]")

    # 4. 文案
    copy_data = None
    if not skip_copy:
        copy_data = generate_copy(tx["transcript"], cfg, out_dir)

    summary = {
        "job_dir": str(out_dir),
        "source_video": str(raw_copy),
        "work_video": str(work_video),
        "final_video": str(final_video),
        "srt": str(tx["srt_path"]),
        "transcript": str(tx["transcript_path"]),
        "promo_copy": str(out_dir / "promo_copy.md") if copy_data else None,
    }

    summary_path = out_dir / "summary.json"
    import json
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"\n[bold green]全部完成[/bold green] 输出目录: {out_dir}")
    return summary
