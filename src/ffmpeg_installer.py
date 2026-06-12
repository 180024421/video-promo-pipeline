from __future__ import annotations

import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

from .config_loader import ROOT, load_config, save_config

console = Console()

FFMPEG_ESSENTIALS_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_DOWNLOAD_URLS = [
    FFMPEG_ESSENTIALS_URL,
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
]
DOWNLOAD_RETRIES = 3
TOOLS_DIR = ROOT / "tools" / "ffmpeg"
ZIP_CACHE = ROOT / "tools" / "ffmpeg-release-essentials.zip"


def ffmpeg_exe_path() -> Path:
    return TOOLS_DIR / "bin" / "ffmpeg.exe"


def is_ffmpeg_ready(cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_config()
    custom = (cfg.get("ffmpeg") or {}).get("path") or ""
    if custom and Path(custom).exists():
        return True
    if shutil.which("ffmpeg"):
        return True
    return ffmpeg_exe_path().exists()


def resolve_installed_path() -> str | None:
    if ffmpeg_exe_path().exists():
        return str(ffmpeg_exe_path())
    return None


ProgressCallback = Callable[[str, int], None] | None


def _report(cb: ProgressCallback, msg: str, pct: int) -> None:
    console.print(f"[cyan]{msg}[/cyan]" if pct < 100 else f"[green]{msg}[/green]")
    if cb:
        cb(msg, pct)


def download_zip(cb: ProgressCallback = None, urls: list[str] | None = None) -> Path:
    """下载 FFmpeg 压缩包到 tools/ 目录，支持多镜像与重试。"""
    TOOLS_DIR.parent.mkdir(parents=True, exist_ok=True)
    candidates = urls or FFMPEG_DOWNLOAD_URLS
    last_err: Exception | None = None

    def _hook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        done = block_num * block_size
        pct = min(85, int(done / total_size * 85))
        _report(cb, f"下载中… {pct}%", pct)

    for url in candidates:
        for attempt in range(1, DOWNLOAD_RETRIES + 1):
            try:
                _report(cb, f"下载 FFmpeg（{attempt}/{DOWNLOAD_RETRIES}）…", 0)
                urllib.request.urlretrieve(url, ZIP_CACHE, _hook)
                _report(cb, "下载完成", 90)
                return ZIP_CACHE
            except Exception as e:
                last_err = e
                _report(cb, f"下载失败，重试… ({e})", min(attempt * 10, 50))
    raise RuntimeError(f"FFmpeg 下载失败: {last_err}")


def extract_and_configure(cb: ProgressCallback = None) -> dict[str, Any]:
    """解压并写入 config.yaml 的 ffmpeg.path。"""
    if not ZIP_CACHE.exists():
        download_zip(cb)

    _report(cb, "解压中…", 92)
    extract_root = ROOT / "tools" / "_ffmpeg_extract"
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_CACHE, "r") as zf:
        zf.extractall(extract_root)

    exe_found: Path | None = None
    for p in extract_root.rglob("ffmpeg.exe"):
        exe_found = p
        break
    if not exe_found:
        raise RuntimeError("压缩包内未找到 ffmpeg.exe")

    bin_dir = exe_found.parent
    if TOOLS_DIR.exists():
        shutil.rmtree(TOOLS_DIR, ignore_errors=True)
    TOOLS_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bin_dir, TOOLS_DIR / "bin")

    _report(cb, "写入配置…", 96)
    cfg = load_config()
    cfg.setdefault("ffmpeg", {})["path"] = str(ffmpeg_exe_path()).replace("\\", "/")
    save_config(cfg)

    shutil.rmtree(extract_root, ignore_errors=True)
    _report(cb, "FFmpeg 安装完成", 100)

    return {
        "ok": True,
        "path": str(ffmpeg_exe_path()),
        "config": str(ROOT / "config.yaml"),
    }


def install_ffmpeg(cb: ProgressCallback = None) -> dict[str, Any]:
    """下载 + 解压 + 配置一条龙。"""
    if ffmpeg_exe_path().exists():
        cfg = load_config()
        cfg.setdefault("ffmpeg", {})["path"] = str(ffmpeg_exe_path()).replace("\\", "/")
        save_config(cfg)
        _report(cb, "FFmpeg 已存在，已同步配置", 100)
        return {"ok": True, "path": str(ffmpeg_exe_path()), "skipped": True}

    download_zip(cb)
    return extract_and_configure(cb)
