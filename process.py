#!/usr/bin/env python3
"""本地录屏视频处理：字幕 + 粗剪 + 烧录 + LM Studio 文案。"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.pipeline import run_pipeline
from src.preflight import run_preflight
from src.config_loader import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="本地视频推广流水线 v2")
    parser.add_argument("video", type=Path, nargs="?", help="录制的视频文件路径 (.mp4/.mkv)")
    parser.add_argument("--config", type=Path, default=None, help="配置文件路径，默认 config.yaml")
    parser.add_argument("--job-dir", type=Path, default=None, help="指定/续跑任务输出目录")
    parser.add_argument("--skip-cut", action="store_true", help="跳过 Auto-Editor 粗剪")
    parser.add_argument("--skip-burn", action="store_true", help="跳过 FFmpeg 烧录字幕")
    parser.add_argument("--skip-copy", action="store_true", help="跳过 LM Studio 文案生成")
    parser.add_argument("--only-transcribe", action="store_true", help="仅转写字幕，不粗剪/烧录/文案")
    parser.add_argument("--only-copy", action="store_true", help="仅根据已有 transcript 生成文案")
    parser.add_argument("--preflight", action="store_true", help="运行前检查 FFmpeg / LM Studio 等")
    parser.add_argument("--force", action="store_true", help="忽略断点续跑，强制重新执行各步骤")
    args = parser.parse_args()

    if args.only_copy:
        if not args.job_dir:
            parser.error("--only-copy 需要配合 --job-dir 指定已有任务目录")
        run_pipeline(
            args.job_dir,
            only_copy=True,
            config_path=args.config,
            job_dir=args.job_dir,
            preflight=args.preflight,
        )
        return

    if args.preflight and not args.video:
        cfg = load_config(args.config)
        ok = run_preflight(cfg)
        raise SystemExit(0 if ok else 1)

    if not args.video:
        parser.error("请提供 video 路径，或使用 --preflight / --only-copy")

    run_pipeline(
        args.video,
        skip_cut=args.skip_cut,
        skip_burn=args.skip_burn,
        skip_copy=args.skip_copy,
        only_transcribe=args.only_transcribe,
        config_path=args.config,
        job_dir=args.job_dir,
        preflight=args.preflight,
        force=args.force,
    )


if __name__ == "__main__":
    main()
