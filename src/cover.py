from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def generate_cover(title: str, cfg: dict[str, Any], out_dir: Path, copy_data: dict[str, Any] | None = None) -> Path | None:
    ccfg = cfg.get("cover") or {}
    if not ccfg.get("enabled", True):
        return None

    if copy_data:
        b = copy_data.get("bilibili") or {}
        titles = b.get("titles") or []
        if titles:
            title = titles[0]
        x = copy_data.get("xiaohongshu") or {}
        if not title and x.get("title"):
            title = x["title"]
    if not title:
        title = "技术分享"

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        console.print("[yellow]缺少 Pillow，跳过封面[/yellow]")
        return None

    w = int(ccfg.get("width", 1280))
    h = int(ccfg.get("height", 720))
    bg = ccfg.get("bg_color", "#1a1a2e")
    fg = ccfg.get("text_color", "#eaeaea")
    accent = ccfg.get("accent_color", "#4cc9f0")

    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    try:
        font_big = ImageFont.truetype("msyh.ttc", 56)
        font_sub = ImageFont.truetype("msyh.ttc", 28)
    except OSError:
        font_big = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    draw.rectangle([(40, h - 12), (w - 40, h - 8)], fill=accent)
    # wrap title
    lines: list[str] = []
    buf = ""
    for ch in title:
        buf += ch
        if len(buf) >= 14:
            lines.append(buf)
            buf = ""
    if buf:
        lines.append(buf)
    y = h // 2 - len(lines) * 30
    for line in lines[:3]:
        draw.text((60, y), line, fill=fg, font=font_big)
        y += 70
    draw.text((60, h - 80), "技术干货 · 已脱敏", fill=accent, font=font_sub)

    out_path = out_dir / "cover.png"
    img.save(out_path)
    (out_dir / "cover_meta.json").write_text(json.dumps({"title": title}, ensure_ascii=False), encoding="utf-8")
    console.print(f"[green]封面已生成[/green] {out_path}")
    return out_path
