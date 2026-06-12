from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .sensitive_scan import scan_copy_sensitive


def run_publish_preflight(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """发布前预审：时长、分辨率、敏感词、封面、字幕文件等。"""
    pcfg = cfg.get("publish_preflight") or {}
    if not pcfg.get("enabled", True):
        return {"skipped": True}

    checks: list[dict[str, Any]] = []
    summary_path = job_dir / "summary.json"
    if not summary_path.exists():
        return {"ok": False, "checks": [{"name": "summary", "ok": False, "msg": "缺少 summary.json"}]}

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    video_path = summary.get("final_video") or summary.get("short_video")
    if video_path and Path(str(video_path)).exists():
        vp = Path(str(video_path))
        size_mb = vp.stat().st_size / (1024 * 1024)
        max_mb = float(pcfg.get("max_size_mb", 2048))
        checks.append({
            "name": "file_size",
            "ok": size_mb <= max_mb,
            "msg": f"{size_mb:.1f} MB (上限 {max_mb} MB)",
        })
        try:
            from .ffmpeg_utils import probe_duration, probe_media
            dur = probe_duration(cfg, vp)
            min_d = float(pcfg.get("min_duration_sec", 10))
            max_d = float(pcfg.get("max_duration_sec", 7200))
            checks.append({
                "name": "duration",
                "ok": min_d <= dur <= max_d,
                "msg": f"{dur:.0f}s",
            })
            meta = probe_media(cfg, vp)
            w = int(meta.get("width") or 0)
            h = int(meta.get("height") or 0)
            checks.append({"name": "resolution", "ok": w >= 720, "msg": f"{w}x{h}"})
        except Exception as e:
            checks.append({"name": "probe", "ok": False, "msg": str(e)})
    else:
        checks.append({"name": "video", "ok": False, "msg": "未找到成片视频"})

    cover = summary.get("cover")
    if pcfg.get("require_cover", False):
        checks.append({
            "name": "cover",
            "ok": bool(cover and Path(str(cover)).exists()),
            "msg": "封面已生成" if cover else "缺少封面",
        })

    srt = job_dir / "subtitle.srt"
    checks.append({"name": "subtitle", "ok": srt.exists(), "msg": "字幕文件"})

    promo_path = job_dir / "promo_copy.json"
    if promo_path.exists():
        promo = json.loads(promo_path.read_text(encoding="utf-8"))
        scan = scan_copy_sensitive(promo, cfg)
        checks.append({
            "name": "sensitive",
            "ok": not scan.get("hits"),
            "msg": f"命中 {len(scan.get('hits', []))} 处" if scan.get("hits") else "通过",
        })

    qc_path = job_dir / "qc_report.json"
    if qc_path.exists():
        qc = json.loads(qc_path.read_text(encoding="utf-8"))
        checks.append({
            "name": "video_qc",
            "ok": qc.get("ok", True),
            "msg": "; ".join((qc.get("issues") or []) + (qc.get("warnings") or [])) or "通过",
        })

    ok = all(c["ok"] for c in checks)
    report = {"ok": ok, "checks": checks}
    (job_dir / "publish_preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
