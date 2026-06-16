from __future__ import annotations

from src.config_wizard import apply_wizard_answers, build_wizard_template
from src.cloud_storage import upload_job_output, upload_to_storage as cloud_upload_to_storage
from src.finetune_deep import export_feedback_for_training
from src.publish_analytics import analytics_summary, record_analytics
from src.scene_detect import detect_scene_changes
from src.audio_enhance import apply_audio_enhance
from src.subtitle_editor import (
    delete_segment,
    load_subtitle_segments,
    merge_segments,
    save_subtitle_segments,
    split_segment,
    update_segment_text,
    update_segment_time,
)
from src.video_player import generate_hls, generate_thumbnail, generate_thumbnails_sprite
from src.persistence import list_jobs, step_timing_aggregate
from src.pipeline_viz import pipeline_dag_json


def test_subtitle_editor(tmp_path):
    p = tmp_path / "seg.json"
    import json

    p.write_text(json.dumps([{"start": 0.0, "end": 5.0, "text": "hello"}, {"start": 5.0, "end": 10.0, "text": "world"}]))
    segs = load_subtitle_segments(p)
    assert len(segs) == 2
    merged = merge_segments(0, 1, segs)
    assert len(merged) == 1
    assert merged[0]["text"] == "hello world"


def test_pipeline_dag():
    import json

    dag = json.loads(pipeline_dag_json())
    assert "nodes" in dag
    assert "edges" in dag
    assert any(d["from"] == "transcribe" for d in dag["edges"])


def test_config_wizard():
    tmpl = build_wizard_template()
    assert len(tmpl["steps"]) == 5
    cfg = {"whisper": {"model": "tiny"}}
    new_cfg = apply_wizard_answers(cfg, {"whisper.model": "small"})
    assert new_cfg["whisper"]["model"] == "small"
