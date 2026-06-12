"""v3.4 功能测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config_io import export_config_bundle, import_config_bundle
from src.health import check_health
from src.hot_topics import inject_hot_topics
from src.job_logger import log_job, read_job_log
from src.resume_from import at_or_past, suggest_resume_step
from src.sensitive_scan import scan_copy_sensitive
from src.video_quality import PRESETS, ffmpeg_video_args, resolve_quality


def test_video_quality_presets():
    cfg = {"video_quality": {"preset": "quality"}}
    q = resolve_quality(cfg)
    assert q["crf"] == 18
    args = ffmpeg_video_args(cfg)
    assert "libx264" in args


def test_resume_from_step():
    assert at_or_past("copy", "transcribe") is True
    assert at_or_past("cut", "transcribe") is False
    assert suggest_resume_step({"current": "配音解说"}) == "dub"


def test_hot_topics_inject():
    cfg = {"hot_topics": {"enabled": True, "custom": ["AI剪辑"], "max_inject": 2}}
    topics = inject_hot_topics(cfg)
    assert any("AI" in t for t in topics)


def test_sensitive_scan():
    cfg = {
        "copy": {"general": {"global_forbidden_words": ["外挂"]}},
        "sensitive_scan": {"enabled": True},
    }
    r = scan_copy_sensitive({"bilibili": {"title": "正常标题"}}, cfg)
    assert r["ok"] is True
    r2 = scan_copy_sensitive({"bilibili": {"title": "这里有外挂"}}, cfg)
    assert r2["ok"] is False


def test_job_logger(tmp_path: Path):
    log_job(tmp_path, "hello")
    text = read_job_log(tmp_path)
    assert "hello" in text


def test_config_io_roundtrip(tmp_path: Path, monkeypatch):
    from src import config_io
    monkeypatch.setattr(config_io, "ROOT", tmp_path)
    cfg = {"whisper": {"model": "tiny"}, "web": {"port": 8766}}
    monkeypatch.setattr(config_io, "load_config", lambda: cfg)
    saved = []
    monkeypatch.setattr(config_io, "save_config", lambda d: saved.append(d) or tmp_path / "config.yaml")
    p = export_config_bundle(cfg)
    assert p.exists()
    import_config_bundle(p, merge=False)
    assert saved


def test_health_check():
    r = check_health({"output": {"dir": "output"}, "batch": {"watch_dir": "watch_in"}})
    assert "checks" in r
    assert "disk_free_gb" in r["checks"]
