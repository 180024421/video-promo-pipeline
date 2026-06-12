import json
from pathlib import Path

from src.export_pack import pack_job_zip
from src.publish_pack import build_publish_pack
from src.soft_export import export_soft_subtitle_package


def test_e2e_publish_pack(tmp_path: Path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"x")
    srt = tmp_path / "subtitle.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    (tmp_path / "transcript.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "promo_copy.json").write_text(json.dumps({
        "bilibili": {"titles": ["T"], "description": "D", "recommended_title": "T"},
        "xiaohongshu": {"title": "X", "body": "B", "topics": ["#a"]},
    }), encoding="utf-8")
    (tmp_path / "summary.json").write_text(json.dumps({"final_video": str(video)}), encoding="utf-8")
    cfg = {"pipeline": {"subtitle_mode": "soft"}, "export": {"zip_enabled": True}}
    export_soft_subtitle_package(video, srt, tmp_path, cfg)
    pack = build_publish_pack(tmp_path, cfg)
    assert "clipboard" in pack
    z = pack_job_zip(tmp_path, cfg)
    assert z and z.exists()
