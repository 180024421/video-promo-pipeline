from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def export_subtitle_pdf(segments: list[dict[str, Any]], cfg: dict[str, Any], out_dir: Path, stem: str = "subtitle") -> Path | None:
    scfg = cfg.get("subtitle") or {}
    if not scfg.get("export_pdf", False):
        return None
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError:
        console.print("[yellow]export_pdf 需要 reportlab: pip install reportlab[/yellow]")
        return None

    pdf_path = out_dir / f"{stem}.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    w, h = A4
    try:
        pdfmetrics.registerFont(TTFont("YaHei", "msyh.ttc"))
        font = "YaHei"
    except Exception:
        font = "Helvetica"

    y = h - 50
    c.setFont(font, 12)
    c.drawString(50, y, "字幕稿")
    y -= 30
    c.setFont(font, 10)
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        line = f"[{_fmt(seg['start'])} - {_fmt(seg['end'])}] {text}"
        if y < 60:
            c.showPage()
            c.setFont(font, 10)
            y = h - 50
        c.drawString(50, y, line[:90])
        y -= 16
    c.save()
    console.print(f"[green]PDF 字幕[/green] {pdf_path}")
    return pdf_path


def _fmt(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"
