from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def generate_cover_variants(
    title: str,
    cfg: dict[str, Any],
    out_dir: Path,
    copy_data: dict[str, Any] | None = None,
    *,
    source_video: Path | None = None,
) -> list[Path]:
    """生成 2~3 张封面 A/B 变体。"""
    from .cover import generate_cover

    ccfg = cfg.get("cover") or {}
    if not ccfg.get("ab_enabled", False):
        p = generate_cover(title, cfg, out_dir, copy_data, source_video=source_video)
        return [p] if p else []

    titles: list[str] = [title]
    if copy_data:
        b = copy_data.get("bilibili") or {}
        titles = list(b.get("titles") or [])[:3]
        if b.get("recommended_title"):
            titles.insert(0, b["recommended_title"])
    accents = ["#4cc9f0", "#e94560", "#ffd700"]
    paths: list[Path] = []
    for i, t in enumerate(titles[:3]):
        vcfg = {**cfg, "cover": {**ccfg, "accent_color": accents[i % len(accents)]}}
        out_path = out_dir / f"cover_{i + 1}.png"
        p = generate_cover(t, vcfg, out_dir, copy_data, source_video=source_video)
        if p and p.exists():
            if p.name != out_path.name:
                import shutil
                shutil.copy2(p, out_path)
            paths.append(out_path)
    console.print(f"[green]封面 A/B[/green] {len(paths)} 张")
    return paths
