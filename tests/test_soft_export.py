from pathlib import Path

from src.soft_export import export_soft_subtitle_package


def test_soft_export(tmp_path: Path):
    video = tmp_path / "demo.mp4"
    srt = tmp_path / "subtitle.srt"
    video.write_bytes(b"fake")
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    cfg = {"pipeline": {"subtitle_mode": "soft"}}
    out = export_soft_subtitle_package(video, srt, tmp_path, cfg)
    assert out is not None
    assert (out / "demo_soft.mp4").exists()
    assert (out / "subtitle.srt").exists()
