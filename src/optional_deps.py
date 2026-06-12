from __future__ import annotations

import subprocess
import sys
from typing import Any

from rich.console import Console

console = Console()

PACKAGES = {
    "whisperx": ("whisperx", "WhisperX 字级对齐"),
    "opencv": ("opencv-python-headless", "人脸竖屏裁剪"),
    "pyannote": ("pyannote.audio", "说话人分离（需 HF token）"),
    "reportlab": ("reportlab", "字幕 PDF 导出"),
    "qrcode": ("qrcode[pil]", "封面二维码"),
}


def check_optional() -> dict[str, bool]:
    out: dict[str, bool] = {}
    for key, (pkg, _) in PACKAGES.items():
        mod = pkg.split("[")[0].replace("-", "_")
        if key == "opencv":
            mod = "cv2"
        if key == "pyannote":
            mod = "pyannote"
        try:
            __import__(mod)
            out[key] = True
        except ImportError:
            out[key] = False
    return out


def install_optional(keys: list[str] | None = None) -> dict[str, Any]:
    keys = keys or list(PACKAGES.keys())
    results: dict[str, Any] = {}
    for key in keys:
        spec = PACKAGES.get(key)
        if not spec:
            results[key] = {"ok": False, "error": "unknown package"}
            continue
        pkg, label = spec
        console.print(f"[cyan]安装[/cyan] {label} ({pkg})")
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg],
            capture_output=True,
            text=True,
        )
        results[key] = {
            "ok": proc.returncode == 0,
            "package": pkg,
            "stdout": (proc.stdout or "")[-2000:],
            "stderr": (proc.stderr or "")[-2000:],
        }
    return results
