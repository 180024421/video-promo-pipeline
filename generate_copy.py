#!/usr/bin/env python3
"""仅根据转写文本生成 B站/小红书推广文案（需 LM Studio 本地服务）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config_loader import load_config, output_dir
from src.copywriter import generate_copy
from src.cover import generate_cover
from src.transcribe import build_chapter_outline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", type=Path, help="transcript.txt 路径")
    parser.add_argument("-o", "--out-dir", type=Path, default=None, help="输出目录")
    parser.add_argument("--segments", type=Path, default=None, help="segments.json（用于章节摘要）")
    args = parser.parse_args()

    cfg = load_config()
    text = args.transcript.read_text(encoding="utf-8")
    out = args.out_dir or args.transcript.parent
    if args.transcript.name == "transcript.txt" and args.transcript.parent.name:
        out = args.transcript.parent
    elif not args.out_dir:
        out = output_dir(cfg, "copy_only")

    chapter_outline = ""
    seg_path = args.segments or (out / "segments.json")
    if seg_path.exists():
        data = json.loads(seg_path.read_text(encoding="utf-8"))
        segments = data.get("segments", []) if isinstance(data, dict) else []
        chapter_outline = build_chapter_outline(segments)

    copy_data = generate_copy(text, cfg, out, chapter_outline=chapter_outline)
    generate_cover(args.transcript.stem, cfg, out, copy_data)


if __name__ == "__main__":
    main()
