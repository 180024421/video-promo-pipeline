from __future__ import annotations

from pathlib import Path

from src.batch_dag import BatchNode, next_runnable, save_batch_plan
from src.compare_player import list_video_variants
from src.job_index import job_created, list_indexed_jobs
from src.smart_cut import _build_clip_prompt
from src.subtitle_collab import acquire_lock, release_lock
from src.vertical_series import plan_vertical_series


def test_scene_hints_in_prompt():
    prompt = _build_clip_prompt("hello", [{"start": 0, "end": 5, "text": "hi"}], {}, scene_hints=[1.5, 3.0])
    assert "1.5s" in prompt


def test_batch_dag_next():
    nodes = [
        BatchNode(video="a.mp4", job_name="j1", status="done"),
        BatchNode(video="b.mp4", job_name="", status="pending", depends_on=["j1"]),
    ]
    n = next_runnable(nodes)
    assert n and n.video == "b.mp4"


def test_vertical_series_plan():
    segs = [{"start": 0, "end": 90, "text": "a"}]
    plans = plan_vertical_series(segs, {"clip_short": {"multi_clip_count": 3}})
    assert len(plans) == 3


def test_subtitle_collab_lock():
    r1 = acquire_lock("job1", 0, "userA")
    assert r1["ok"]
    r2 = acquire_lock("job1", 0, "userB")
    assert not r2["ok"]
    release_lock("job1", 0, "userA")


def test_compare_variants(tmp_path):
    (tmp_path / "demo_cut.mp4").write_bytes(b"x")
    v = list_video_variants(tmp_path)
    assert any("粗剪" in x["label"] or "_cut" in x["name"] for x in v)


def test_job_index():
    job_created("test_index_job_v40")
    jobs = list_indexed_jobs(limit=200)
    assert any(j["name"] == "test_index_job_v40" for j in jobs)
