from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def check_health(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from .config_loader import ROOT, load_config
    from .ffmpeg_installer import is_ffmpeg_ready
    from .service_checks import check_lm_studio_detail

    cfg = cfg or load_config()
    out: dict[str, Any] = {"ok": True, "checks": {}}

    out["checks"]["ffmpeg"] = is_ffmpeg_ready(cfg)
    try:
        import faster_whisper  # noqa: F401
        out["checks"]["whisper"] = True
    except ImportError:
        out["checks"]["whisper"] = False
        out["ok"] = False

    out["checks"]["lm_studio"] = check_lm_studio_detail(cfg).get("ok", False)

    out_dir = ROOT / cfg.get("output", {}).get("dir", "output")
    usage = shutil.disk_usage(out_dir if out_dir.exists() else ROOT)
    free_gb = usage.free / (1024 ** 3)
    out["checks"]["disk_free_gb"] = round(free_gb, 2)
    out["checks"]["disk_ok"] = free_gb > 2.0
    if free_gb <= 2.0:
        out["ok"] = False

    watch = ROOT / (cfg.get("batch") or {}).get("watch_dir", "watch_in")
    out["checks"]["watch_dir"] = str(watch)
    out["checks"]["watch_pending"] = len(list(watch.glob("*.mp4"))) if watch.exists() else 0

    return out
