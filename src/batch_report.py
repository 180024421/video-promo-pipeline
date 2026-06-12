from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .timing_stats import load_timing_stats


def build_batch_report(output_dir: Path, watch_dir: Path | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if not output_dir.exists():
        return {"generated_at": datetime.now().isoformat(), "jobs": [], "summary": {}}

    for d in sorted(output_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        summary_path = d / "summary.json"
        status = "unknown"
        error = ""
        if summary_path.exists():
            try:
                s = json.loads(summary_path.read_text(encoding="utf-8"))
                status = "done" if s else "done"
            except Exception:
                status = "error"
        prog_path = d / "pipeline_progress.json"
        if prog_path.exists():
            try:
                prog = json.loads(prog_path.read_text(encoding="utf-8"))
                if prog.get("current") == "完成":
                    status = "done"
                elif prog.get("error"):
                    status = "error"
                    error = prog.get("error", "")
                else:
                    status = "partial"
            except Exception:
                pass
        timing = load_timing_stats(d) or {}
        rows.append({
            "name": d.name,
            "status": status,
            "error": error,
            "total_seconds": timing.get("total_seconds", 0),
            "mtime": datetime.fromtimestamp(d.stat().st_mtime).isoformat(),
        })

    done = sum(1 for r in rows if r["status"] == "done")
    failed = sum(1 for r in rows if r["status"] == "error")
    return {
        "generated_at": datetime.now().isoformat(),
        "watch_dir": str(watch_dir) if watch_dir else "",
        "jobs": rows[:100],
        "summary": {"total": len(rows), "done": done, "failed": failed, "partial": len(rows) - done - failed},
    }


def export_batch_report_html(report: dict[str, Any], dest: Path) -> Path:
    rows = report.get("jobs") or []
    trs = "".join(
        f"<tr><td>{r['name']}</td><td>{r['status']}</td><td>{r.get('total_seconds', 0)}</td><td>{r.get('error', '')}</td></tr>"
        for r in rows
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>批量报告</title>
<style>body{{font-family:sans-serif;padding:1rem}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:6px}}</style></head><body>
<h1>批量处理报告</h1><p>生成于 {report.get('generated_at')}</p>
<p>完成 {report.get('summary', {}).get('done', 0)} / 失败 {report.get('summary', {}).get('failed', 0)}</p>
<table><tr><th>任务</th><th>状态</th><th>耗时(s)</th><th>错误</th></tr>{trs}</table></body></html>"""
    dest.write_text(html, encoding="utf-8")
    return dest
