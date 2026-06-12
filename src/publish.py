from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from .bilibili_upload import upload_video_bilibili

console = Console()


def publish_bilibili(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    pcfg = (cfg.get("publish") or {}).get("bilibili") or {}
    if not pcfg.get("enabled", False):
        return {"skipped": True, "reason": "未启用 bilibili 发布"}

    summary_path = job_dir / "summary.json"
    if not summary_path.exists():
        return {"error": "缺少 summary.json"}

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    video = summary.get("final_video") or summary.get("short_video")
    title_path = job_dir / "bilibili_description.txt"
    promo_path = job_dir / "promo_copy.json"
    title = job_dir.name.split("_")[0]
    if promo_path.exists():
        promo = json.loads(promo_path.read_text(encoding="utf-8"))
        b = promo.get("bilibili") or {}
        title = b.get("recommended_title") or (b.get("titles") or [title])[0]
    desc = title_path.read_text(encoding="utf-8") if title_path.exists() else ""

    manifest: dict[str, Any] = {
        "platform": "bilibili",
        "video": video,
        "title": title,
        "description": desc[:2000],
        "status": "ready",
    }

    has_creds = bool(
        pcfg.get("client_id") or pcfg.get("access_key")
    ) and bool(pcfg.get("client_secret") or pcfg.get("secret") or pcfg.get("refresh_token"))

    if pcfg.get("auto_upload", False) and video and Path(str(video)).exists():
        up = upload_video_bilibili(Path(str(video)), title, desc, cfg, job_dir=job_dir)
        manifest.update(up)
        prog = job_dir / "bilibili_upload_progress.json"
        if prog.exists():
            manifest["upload_progress"] = json.loads(prog.read_text(encoding="utf-8"))
    elif not has_creds:
        manifest["note"] = "配置 client_id/client_secret/refresh_token 后可 auto_upload"

    out = job_dir / "publish_bilibili.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]B站发布清单[/green] {out}")
    return manifest


def publish_douyin(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    pcfg = (cfg.get("publish") or {}).get("douyin") or {}
    if not pcfg.get("enabled", False):
        return {"skipped": True, "reason": "未启用 douyin 发布"}

    summary_path = job_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    video = summary.get("short_video") or summary.get("final_video")
    promo = job_dir / "promo_copy.json"
    title, body = job_dir.name.split("_")[0], ""
    if promo.exists():
        data = json.loads(promo.read_text(encoding="utf-8"))
        d = data.get("douyin") or {}
        title = d.get("title", title)
        body = d.get("body", body)

    manifest = {
        "platform": "douyin",
        "video": video,
        "title": title,
        "body": body,
        "status": "ready",
        "note": "抖音开放平台需企业资质；当前输出 manifest 供对接",
    }
    out = job_dir / "publish_douyin.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]抖音发布清单[/green] {out}")
    return manifest


def run_publish(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    pub_cfg = cfg.get("publish") or {}
    if not pub_cfg.get("enabled", False):
        return {}
    results = {}
    if (pub_cfg.get("bilibili") or {}).get("enabled"):
        results["bilibili"] = publish_bilibili(job_dir, cfg)
    if (pub_cfg.get("douyin") or {}).get("enabled"):
        results["douyin"] = publish_douyin(job_dir, cfg)
    return results
