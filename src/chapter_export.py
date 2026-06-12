from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .chapters import build_chapters_from_segments


def export_chapter_markers(segments: list[dict[str, Any]], cfg: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    chapters = build_chapters_from_segments(segments, cfg)
    if not chapters:
        return {}

    outputs: dict[str, Path] = {}
    # B 站简介章节格式
    bili_lines = [f"{c['time']} {c['title']}" for c in chapters]
    bili_path = out_dir / "chapters_bilibili.txt"
    bili_path.write_text("\n".join(bili_lines), encoding="utf-8")
    outputs["bilibili"] = bili_path

    # YouTube 章节（视频描述内）
    yt_lines = [f"{c['time']} {c['title']}" for c in chapters]
    yt_path = out_dir / "chapters_youtube.txt"
    yt_path.write_text("\n".join(yt_lines), encoding="utf-8")
    outputs["youtube"] = yt_path

    json_path = out_dir / "chapters.json"
    json_path.write_text(json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8")
    outputs["json"] = json_path
    return outputs
