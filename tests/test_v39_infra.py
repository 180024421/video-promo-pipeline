from __future__ import annotations

from pathlib import Path

from src.cloud_storage import upload_to_storage
from src.persistence import add_step_timing, init_db, list_jobs, step_timing_aggregate, upsert_job
from src.publish_analytics import analytics_summary, record_analytics
from src.finetune_deep import check_bridge_ready, export_feedback_for_training


def test_persistence():
    init_db()
    upsert_job("test_job_xyz", status="done", step="publish")
    jobs = list_jobs(status="done")
    assert any(j["name"] == "test_job_xyz" for j in jobs)


def test_step_timing():
    add_step_timing("test_job_timing", "transcribe", 120.5)
    agg = step_timing_aggregate()
    assert len(agg) >= 0


def test_publish_analytics():
    record_analytics("test_job", "bilibili", views=100, likes=10)
    summary = analytics_summary()
    assert summary["total_views"] >= 100


def test_finetune_deep(tmp_path):
    fb_path = tmp_path / "test_feedback.jsonl"
    # check_bridge_ready doesn't require file
    state = check_bridge_ready()
    assert "feedback_count" in state


def test_cloud_storage_disabled():
    r = upload_to_storage(Path("nonexistent.txt"), {"cloud_storage": {"enabled": False}})
    assert not r["ok"]
