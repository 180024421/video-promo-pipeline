from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

_PLATFORMS = {
    "weixin_channels": {
        "upload_url": "https://channels.weixin.qq.com/",
        "post_file": "weixin_channels_post.txt",
        "max_title": 30,
    },
    "kuaishou": {
        "upload_url": "https://cp.kuaishou.com/article/publish/video",
        "post_file": "kuaishou_post.txt",
        "max_title": 30,
    },
}


def build_extra_platform_pack(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    ecfg = cfg.get("platform_extra") or {}
    if not ecfg.get("enabled", True):
        return {}
    promo = {}
    if (job_dir / "promo_copy.json").exists():
        promo = json.loads((job_dir / "promo_copy.json").read_text(encoding="utf-8"))
    results: dict[str, Any] = {}
    for name, meta in _PLATFORMS.items():
        if not ecfg.get(name, {}).get("enabled", True):
            continue
        pdata = promo.get(name) or {}
        body = ""
        pf = job_dir / meta["post_file"]
        if pf.exists():
            body = pf.read_text(encoding="utf-8")
        manifest = {
            "platform": name,
            "upload_url": meta["upload_url"],
            "title": (pdata.get("title") or "")[: meta["max_title"]],
            "body": body,
            "clipboard": f"{pdata.get('title', '')}\n\n{body}",
        }
        out = job_dir / f"publish_{name}.json"
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        results[name] = manifest
    return results
