#!/usr/bin/env python3
"""本地录屏视频处理：字幕 + 粗剪 + 烧录 + LM Studio 文案。"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="本地视频推广流水线")
    parser.add_argument("video", type=Path, help="录制的视频文件路径 (.mp4/.mkv)")
    parser.add_argument("--config", type=Path, default=None, help="配置文件路径，默认 config.yaml")
    parser.add_argument("--skip-cut", action="store_true", help="跳过 Auto-Editor 粗剪")
    parser.add_argument("--skip-burn", action="store_true", help="跳过 FFmpeg 烧录字幕")
    parser.add_argument("--skip-copy", action="store_true", help="跳过 LM Studio 文案生成")
    args = parser.parse_args()

    run_pipeline(
        args.video,
        skip_cut=args.skip_cut,
        skip_burn=args.skip_burn,
        skip_copy=args.skip_copy,
        config_path=args.config,
    )


if __name__ == "__main__":
    main()
