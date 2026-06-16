"""平台播放数据自动回流。"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from .config_loader import ROOT
from .publish_analytics import record_analytics
from .persistence import record_publish_data


def _fetch_bilibili_stat(bvid: str, cookie: str = "") -> dict[str, Any]:
  """拉取 B 站视频基础数据（需 cookie 时从配置读取）。"""
  url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
  req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
  if cookie:
    req.add_header("Cookie", cookie)
  with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode())
  stat = (data.get("data") or {}).get("stat") or {}
  return {"views": stat.get("view", 0), "likes": stat.get("like", 0), "comments": stat.get("reply", 0)}


def sync_job_stats(job_dir: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
  """从任务 publish 清单同步各平台数据。"""
  results: list[dict[str, Any]] = []
  pub_path = job_dir / "publish_result.json"
  if not pub_path.exists():
    return results
  pub = json.loads(pub_path.read_text(encoding="utf-8"))
  bcfg = (cfg.get("publish") or {}).get("bilibili") or {}
  cookie = bcfg.get("sessdata_cookie", "") or bcfg.get("cookie", "")

  bvid = pub.get("bilibili", {}).get("bvid") or pub.get("bvid", "")
  if bvid:
    try:
      stats = _fetch_bilibili_stat(bvid, cookie)
      record_analytics(job_dir.name, "bilibili", **stats, url=f"https://www.bilibili.com/video/{bvid}")
      record_publish_data(job_dir.name, "bilibili", url=f"https://www.bilibili.com/video/{bvid}", **stats)
      results.append({"platform": "bilibili", **stats})
    except Exception as e:
      results.append({"platform": "bilibili", "error": str(e)})

  yt_id = pub.get("youtube", {}).get("video_id", "")
  if yt_id:
    results.append({"platform": "youtube", "video_id": yt_id, "note": "需 YouTube Data API key 配置后扩展"})

  return results


def sync_all_jobs(output_base: Path, cfg: dict[str, Any], *, limit: int = 20) -> dict[str, Any]:
  synced = 0
  errors: list[str] = []
  if not output_base.exists():
    return {"synced": 0, "errors": []}
  for d in sorted(output_base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
    if not d.is_dir():
      continue
    try:
      r = sync_job_stats(d, cfg)
      if r:
        synced += 1
    except Exception as e:
      errors.append(f"{d.name}: {e}")
  return {"synced": synced, "errors": errors}
