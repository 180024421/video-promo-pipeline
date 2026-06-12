from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from .ffmpeg_utils import resolve_ffmpeg

console = Console()


def extract_frame_at(ffmpeg: str, video_path: Path, ts: float, out_path: Path) -> bool:
    try:
        subprocess.run(
            [ffmpeg, "-y", "-ss", str(ts), "-i", str(video_path), "-vframes", "1", "-q:v", "2", str(out_path)],
            check=True,
            capture_output=True,
        )
        return out_path.exists()
    except subprocess.CalledProcessError:
        return False


def detect_face_crop_x(frame_path: Path, cfg: dict[str, Any]) -> float | None:
    """返回人脸中心 x 比例 0~1；无 OpenCV/人脸时返回 None。"""
    fcfg = (cfg.get("clip_short") or {})
    if fcfg.get("crop_mode") != "face":
        return None
    try:
        import cv2  # type: ignore
    except ImportError:
        console.print("[yellow]人脸裁剪需要 opencv-python[/yellow]")
        return None

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    img = cv2.imread(str(frame_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    if len(faces) == 0:
        return None
    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    cx = (x + fw / 2) / w
    console.print(f"[green]人脸检测[/green] center_x={cx:.2f}")
    return cx


def build_vertical_crop_filter(cfg: dict[str, Any], video_path: Path, ffmpeg: str, at_sec: float, tmp_dir: Path) -> str:
    """构建竖屏 crop 滤镜；face 模式尝试人脸居中。"""
    ccfg = cfg.get("clip_short") or {}
    mode = ccfg.get("crop_mode", "center")
    if mode == "upper":
        return "crop=ih*9/16:ih:(iw-ih*9/16)/2:ih*0.05"
    if mode == "face":
        frame = tmp_dir / "_face_probe.jpg"
        tmp_dir.mkdir(exist_ok=True)
        if extract_frame_at(ffmpeg, video_path, at_sec, frame):
            cx = detect_face_crop_x(frame, cfg)
            if cx is not None:
                # 以人脸为中心裁 9:16
                return f"crop=ih*9/16:ih:max(0\\,min(iw-ih*9/16\\,{cx}*iw-ih*9/32)):0"
    return "crop=ih*9/16:ih:(iw-ih*9/16)/2:0"
