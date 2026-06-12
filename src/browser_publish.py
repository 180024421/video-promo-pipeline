from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def run_browser_publish(job_dir: Path, platform: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Playwright 半自动：打开创作者中心并预填标题（需用户确认发布）。"""
    bcfg = (cfg.get("browser_publish") or {})
    if not bcfg.get("enabled", False):
        return {"skipped": True, "reason": "browser_publish 未启用"}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "请安装 playwright: pip install playwright && playwright install chromium"}

    promo_path = job_dir / "promo_copy.json"
    if not promo_path.exists():
        return {"ok": False, "error": "缺少 promo_copy.json"}

    promo = json.loads(promo_path.read_text(encoding="utf-8"))
    pdata = promo.get(platform) or {}
    title = pdata.get("title") or pdata.get("recommended_title", "")
    body = ""
    post_file = job_dir / f"{platform}_post.txt"
    if post_file.exists():
        body = post_file.read_text(encoding="utf-8")

    urls = {
        "douyin": "https://creator.douyin.com/creator-micro/content/upload",
        "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish",
    }
    url = urls.get(platform)
    if not url:
        return {"ok": False, "error": f"不支持平台 {platform}"}

    headless = bcfg.get("headless", False)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        console.print(f"[cyan]浏览器已打开[/cyan] {platform} — 请手动上传视频并核对预填文案")
        (job_dir / f"browser_publish_{platform}.json").write_text(
            json.dumps({"title": title, "body": body[:500], "url": url, "status": "opened"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if not headless:
            input("完成后按 Enter 关闭浏览器…")
        browser.close()
    return {"ok": True, "platform": platform, "title": title}
