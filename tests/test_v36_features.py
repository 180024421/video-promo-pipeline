from __future__ import annotations

from pathlib import Path

from src.job_queue import cancel_job, enqueue, pause_queue, resume_queue, status
from src.prompt_templates import list_templates, save_template, get_template
from src.rate_limit import check_rate_limit
from src.timing_stats import StepTimer
from src.video_quality import ffmpeg_video_args, resolve_quality


def test_nvenc_encoder():
    cfg = {"video_quality": {"encoder": "h264_nvenc", "preset": "balanced"}}
    args = ffmpeg_video_args(cfg)
    assert "h264_nvenc" in args


def test_step_timer(tmp_path: Path):
    t = StepTimer(tmp_path)
    t.start("转写")
    t.end("转写")
    d = t.finish()
    assert d.get("total_seconds", 0) >= 0


def test_rate_limit():
    ok, _ = check_rate_limit("test-client", max_per_minute=1000)
    assert ok is True


def test_prompt_templates(tmp_path, monkeypatch):
    from src import prompt_templates as pt
    monkeypatch.setattr(pt, "TEMPLATES_DIR", tmp_path)
    save_template("demo", {"name": "Demo", "platform": "bilibili"})
    assert get_template("demo") is not None
    assert any(x["id"] == "demo" for x in list_templates())


def test_queue_cancel():
    enqueue("job-a")
    cancel_job("job-a")
    st = status()
    assert "job-a" in st.get("cancelled", []) or st["jobs"].get("job-a") == "cancelled"
    pause_queue()
    resume_queue()
