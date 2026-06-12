#!/usr/bin/env python3
"""仅根据转写文本生成 B站/小红书推广文案（需 LM Studio 本地服务）。"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config_loader import load_config, output_dir
from src.copywriter import generate_copy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", type=Path, help="transcript.txt 路径")
    parser.add_argument("-o", "--out-dir", type=Path, default=None, help="输出目录")
    args = parser.parse_args()

    cfg = load_config()
    text = args.transcript.read_text(encoding="utf-8")
    out = args.out_dir or output_dir(cfg, "copy_only")
    generate_copy(text, cfg, out)


if __name__ == "__main__":
    main()
