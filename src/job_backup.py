from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def backup_job(job_dir: Path, dest: Path | None = None) -> Path:
    dest = dest or job_dir.parent / f"{job_dir.name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in job_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(job_dir.parent))
    console.print(f"[green]任务备份[/green] {dest}")
    return dest


def restore_job(zip_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()
        if not members:
            raise ValueError("空备份包")
        top = members[0].split("/")[0]
        zf.extractall(output_dir)
    restored = output_dir / top
    console.print(f"[green]任务恢复[/green] {restored}")
    return restored
