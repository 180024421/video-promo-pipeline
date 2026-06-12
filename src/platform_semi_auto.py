from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def build_semi_auto_pack(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """抖音/小红书半自动发布包：文案 + 步骤 + 可选二维码内容。"""
    scfg = cfg.get("platform_semi_auto") or {}
    if not scfg.get("enabled", True):
        return {}

    summary = {}
    sp = job_dir / "summary.json"
    if sp.exists():
        summary = json.loads(sp.read_text(encoding="utf-8"))
    video = summary.get("short_video") or summary.get("final_video")
    promo = {}
    pp = job_dir / "promo_copy.json"
    if pp.exists():
        promo = json.loads(pp.read_text(encoding="utf-8"))

    pack: dict[str, Any] = {
        "video_path": video,
        "platforms": {},
    }

    for platform, upload_url, post_file in (
        ("douyin", "https://creator.douyin.com/", "douyin_post.txt"),
        ("xiaohongshu", "https://creator.xiaohongshu.com/", "xiaohongshu_post.txt"),
    ):
        pdata = promo.get(platform) or {}
        body = ""
        pf = job_dir / post_file
        if pf.exists():
            body = pf.read_text(encoding="utf-8")
        pack["platforms"][platform] = {
            "upload_url": upload_url,
            "title": pdata.get("title", pdata.get("recommended_title", "")),
            "body": body or pdata.get("body", ""),
            "steps": [
                f"1. 打开 {upload_url}",
                "2. 上传竖屏视频（优先 short_video）",
                "3. 粘贴下方标题与正文",
                "4. 添加话题标签后发布",
            ],
            "clipboard": f"{pdata.get('title', '')}\n\n{body}",
        }

    qr_content = scfg.get("qr_content", "")
    if qr_content:
        pack["qr_content"] = qr_content
        try:
            import qrcode  # type: ignore
            img = qrcode.make(qr_content)
            qr_path = job_dir / "publish_qr.png"
            img.save(str(qr_path))
            pack["qr_image"] = str(qr_path)
        except ImportError:
            pack["qr_note"] = "pip install qrcode[pil] 可生成二维码"

    out = job_dir / "semi_auto_publish.json"
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]半自动发布包[/green] {out}")
    return pack
