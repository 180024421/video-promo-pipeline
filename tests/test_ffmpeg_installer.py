from pathlib import Path
from unittest.mock import patch

from src.ffmpeg_installer import FFMPEG_ESSENTIALS_URL, is_ffmpeg_ready


def test_ffmpeg_url():
    assert "ffmpeg" in FFMPEG_ESSENTIALS_URL
    assert FFMPEG_ESSENTIALS_URL.endswith(".zip")


def test_is_ffmpeg_ready_with_path(tmp_path):
    fake = tmp_path / "ffmpeg.exe"
    fake.write_text("", encoding="utf-8")
    cfg = {"ffmpeg": {"path": str(fake)}}
    assert is_ffmpeg_ready(cfg) is True
