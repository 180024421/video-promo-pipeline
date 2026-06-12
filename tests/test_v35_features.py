from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.hot_topics import inject_hot_topics
from src.optional_deps import PACKAGES, check_optional
from src.resume_from import suggest_resume_step
from src.setup_wizard import get_setup_checklist
from src.video_quality import ffmpeg_audio_args, ffmpeg_video_args


def test_video_quality_audio():
    cfg = {"video_quality": {"preset": "fast"}}
    assert "-b:a" in " ".join(ffmpeg_audio_args(cfg))
    assert "copy" in " ".join(ffmpeg_video_args(cfg, copy_video=True))


def test_hot_topics_with_transcript():
    cfg = {"hot_topics": {"enabled": True, "custom": ["AI"], "source": "custom", "max_inject": 2}}
    topics = inject_hot_topics(cfg, "test")
    assert "#AI" in topics


def test_setup_wizard():
    r = get_setup_checklist({"output": {"dir": "output"}, "batch": {"watch_dir": "w"}, "lm_studio": {"enabled": False}})
    assert "steps" in r
    assert len(r["steps"]) >= 4


def test_optional_packages_defined():
    assert "whisperx" in PACKAGES


def test_resume_suggest():
    assert suggest_resume_step({"current": "烧录字幕"}) == "burn"
