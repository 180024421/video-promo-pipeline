from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

DEFAULT_INCLUDE = [
    "*.mp4", "*.mkv", "*.mov",
    "*.srt", "*.vtt", "*.ass",
    "*.txt", "*.md", "*.json", "*.png",
]


def pack_job_zip(job_dir: Path, cfg: dict[str, Any]) -> Path | None:
    ecfg = cfg.get("export") or {}
    if not ecfg.get("zip_enabled", True):
        return None

    patterns = ecfg.get("zip_include", DEFAULT_INCLUDE)
    zip_path = job_dir / f"{job_dir.name}_bundle.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pat in patterns:
            for fp in job_dir.glob(pat):
                if fp.is_file() and fp != zip_path:
                    zf.write(fp, fp.name)
        soft_dir = job_dir / "soft_subtitle"
        if soft_dir.is_dir():
            for fp in soft_dir.iterdir():
                if fp.is_file():
                    zf.write(fp, f"soft_subtitle/{fp.name}")
        manifest = {
            "job": job_dir.name,
            "packed_at": datetime.now().isoformat(),
            "files": [p.name for p in job_dir.iterdir() if p.is_file()],
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    console.print(f"[green]打包完成[/green] {zip_path}")
    return zip_path
