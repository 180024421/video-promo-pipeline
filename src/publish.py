from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from .bilibili_upload import upload_video_bilibili

console = Console()

_MANUAL_BILI = [
    "1. 打开 https://member.bilibili.com/platform/upload/video/frame",
    "2. 上传成片 MP4",
    "3. 粘贴标题与简介（见 bilibili_description.txt）",
    "4. 添加章节（见 bilibili_chapters.txt，如有）",
]

_MANUAL_DOUYIN = [
    "1. 打开抖音创作者中心 / 抖音 APP 发布",
    "2. 上传竖屏短视频（优先 short_video）",
    "3. 粘贴标题与正文（见 promo_copy.json → douyin）",
    "4. 添加话题标签后发布",
]

_MANUAL_XHS = [
    "1. 打开小红书创作者中心",
    "2. 上传竖屏视频或图文",
    "3. 粘贴标题与正文（见 xiaohongshu_post.txt）",
    "4. 添加话题后发布",
]


def _load_promo(job_dir: Path) -> dict[str, Any]:
    p = job_dir / "promo_copy.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


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
    promo = _load_promo(job_dir)
    title = job_dir.name.split("_")[0]
    b = promo.get("bilibili") or {}
    title = b.get("recommended_title") or (b.get("titles") or [title])[0]
    desc = title_path.read_text(encoding="utf-8") if title_path.exists() else ""

    manifest: dict[str, Any] = {
        "platform": "bilibili",
        "video": video,
        "title": title,
        "description": desc[:2000],
        "status": "ready",
        "manual_steps": _MANUAL_BILI,
        "clipboard": {"title": title, "description": desc[:2000]},
    }

    has_creds = bool(pcfg.get("client_id") or pcfg.get("access_key")) and bool(
        pcfg.get("client_secret") or pcfg.get("secret") or pcfg.get("refresh_token")
    )

    if pcfg.get("auto_upload", False) and video and Path(str(video)).exists():
        up = upload_video_bilibili(Path(str(video)), title, desc, cfg, job_dir=job_dir)
        manifest.update(up)
        prog = job_dir / "bilibili_upload_progress.json"
        if prog.exists():
            manifest["upload_progress"] = json.loads(prog.read_text(encoding="utf-8"))
    elif not has_creds:
        manifest["note"] = "配置 OAuth 后可 auto_upload；当前请按 manual_steps 手动发布"

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
    promo = _load_promo(job_dir)
    d = promo.get("douyin") or {}
    title = d.get("title", job_dir.name.split("_")[0])
    body = d.get("body", "")
    post_txt = job_dir / "douyin_post.txt"
    if post_txt.exists():
        body = post_txt.read_text(encoding="utf-8")

    manifest = {
        "platform": "douyin",
        "video": video,
        "title": title,
        "body": body,
        "status": "ready",
        "manual_steps": _MANUAL_DOUYIN,
        "clipboard": {"title": title, "body": body},
        "note": "抖音开放平台需企业资质；使用创作者中心手动发布",
        "upload_url": "https://creator.douyin.com/",
    }
    out = job_dir / "publish_douyin.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]抖音发布清单[/green] {out}")
    return manifest


def publish_xiaohongshu(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    pcfg = (cfg.get("publish") or {}).get("xiaohongshu") or {}
    if not pcfg.get("enabled", False):
        return {"skipped": True, "reason": "未启用 xiaohongshu 发布"}

    summary_path = job_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    video = summary.get("short_video") or summary.get("final_video")
    promo = _load_promo(job_dir)
    x = promo.get("xiaohongshu") or {}
    title = x.get("title", job_dir.name.split("_")[0])
    body = x.get("body", "")
    post_txt = job_dir / "xiaohongshu_post.txt"
    if post_txt.exists():
        body = post_txt.read_text(encoding="utf-8")

    manifest = {
        "platform": "xiaohongshu",
        "video": video,
        "title": title,
        "body": body,
        "status": "ready",
        "manual_steps": _MANUAL_XHS,
        "clipboard": {"title": title, "body": body},
        "upload_url": "https://creator.xiaohongshu.com/",
    }
    out = job_dir / "publish_xiaohongshu.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]小红书发布清单[/green] {out}")
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
    if (pub_cfg.get("xiaohongshu") or {}).get("enabled"):
        results["xiaohongshu"] = publish_xiaohongshu(job_dir, cfg)
    return results
