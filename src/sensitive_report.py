"""敏感内容合规报告。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .sensitive_scan import scan_copy_sensitive


def build_compliance_report(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
  """生成合规扫描报告（文案 + OCR 占位 + 音频关键词占位）。"""
  issues: list[dict[str, Any]] = []
  promo_path = job_dir / "promo_copy.json"
  copy_data: dict[str, Any] = {}
  if promo_path.exists():
    copy_data = json.loads(promo_path.read_text(encoding="utf-8"))
    scan = scan_copy_sensitive(copy_data, cfg)
    issues.extend(scan.get("issues", []))

  transcript = ""
  tp = job_dir / "transcript.txt"
  if tp.exists():
    transcript = tp.read_text(encoding="utf-8")
    scfg = cfg.get("sensitive_scan") or {}
    extra = scfg.get("extra_words", [])
    for w in extra:
      if w and w in transcript:
        issues.append({"path": "transcript", "word": w, "context": "transcript"})

  report = {
    "job": job_dir.name,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "ok": len(issues) == 0,
    "issue_count": len(issues),
    "issues": issues,
    "checks": ["copy_sensitive", "transcript_keywords"],
  }
  out_json = job_dir / "compliance_report.json"
  out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

  out_md = job_dir / "compliance_report.md"
  lines = [f"# 合规报告 — {job_dir.name}", f"生成时间: {report['generated_at']}", ""]
  if report["ok"]:
    lines.append("**结论: 通过**")
  else:
    lines.append(f"**结论: 发现 {len(issues)} 项问题**")
    lines.append("")
    for i, iss in enumerate(issues[:50], 1):
      lines.append(f"{i}. `{iss.get('word')}` @ {iss.get('path')}: {iss.get('context', '')[:80]}")
  out_md.write_text("\n".join(lines), encoding="utf-8")

  try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf_path = job_dir / "compliance_report.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    y = 800
    c.setFont("Helvetica", 12)
    for line in lines[:40]:
      c.drawString(50, y, line[:90])
      y -= 16
      if y < 50:
        c.showPage()
        y = 800
    c.save()
    report["pdf"] = str(pdf_path)
  except ImportError:
    pass

  return report
