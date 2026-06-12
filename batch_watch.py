#!/usr/bin/env python3
"""监控目录，新视频自动进入流水线。"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from rich.console import Console

from src.config_loader import ROOT, load_config
from src.pipeline import run_pipeline

console = Console()

VIDEO_EXT = {".mp4", ".mkv", ".mov", ".webm"}


def scan_pending(watch_dir: Path, done_dir: Path) -> list[Path]:
    pending: list[Path] = []
    for p in sorted(watch_dir.iterdir()):
        if not p.is_file() or p.suffix.lower() not in VIDEO_EXT:
            continue
        marker = done_dir / f"{p.stem}.done"
        if marker.exists():
            continue
        pending.append(p)
    return pending


def main() -> None:
    parser = argparse.ArgumentParser(description="批量监控目录自动处理视频")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--watch-dir", type=Path, default=None, help="监控目录，默认 config batch.watch_dir")
    parser.add_argument("--interval", type=int, default=None, help="轮询秒数")
    parser.add_argument("--once", action="store_true", help="只处理当前队列一次后退出")
    args = parser.parse_args()

    cfg = load_config(args.config)
    bcfg = cfg.get("batch") or {}
    watch_dir = (args.watch_dir or ROOT / bcfg.get("watch_dir", "watch_in")).resolve()
    watch_dir.mkdir(parents=True, exist_ok=True)
    done_dir = watch_dir / ".done"
    done_dir.mkdir(exist_ok=True)
    interval = args.interval or int(bcfg.get("poll_interval_sec", 30))

    console.print(f"[bold]监控目录[/bold] {watch_dir}  间隔 {interval}s")

    while True:
        for video in scan_pending(watch_dir, done_dir):
            console.print(f"\n[cyan]开始处理[/cyan] {video.name}")
            try:
                run_pipeline(video, config_path=args.config, preflight=False)
                (done_dir / f"{video.stem}.done").write_text("ok", encoding="utf-8")
            except Exception as e:
                console.print(f"[red]失败[/red] {video.name}: {e}")
                (done_dir / f"{video.stem}.error").write_text(str(e), encoding="utf-8")
        if args.once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
