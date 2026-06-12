from __future__ import annotations

from pathlib import Path

from src.config_schema import validate_config
from src.job_cancel import check_cancel, clear_cancel, is_cancel_requested, request_cancel
from src.timing_aggregate import aggregate_job_timings
from src.vertical_templates import apply_vertical_template, list_vertical_templates
from src.whisper_prompt import build_whisper_initial_prompt
from src.rag_copy import retrieve_context, save_document


def test_whisper_hotwords():
    cfg = {
        "whisper": {"initial_prompt": "技术讲解", "hotwords": ["Spring Boot", "Redis"], "hotwords_from_terminology": False},
    }
    p = build_whisper_initial_prompt(cfg)
    assert "Spring Boot" in p
    assert "技术讲解" in p


def test_job_cancel():
    request_cancel("job-x")
    assert is_cancel_requested("job-x")
    try:
        check_cancel("job-x")
        assert False
    except RuntimeError:
        pass
    clear_cancel("job-x")
    check_cancel("job-x")


def test_config_validate():
    issues = validate_config({"whisper": {}, "web": {}, "output": {}})
    assert isinstance(issues, list)


def test_vertical_template():
    cfg = apply_vertical_template({"clip_short": {}}, "douyin")
    assert cfg["clip_short"]["height"] == 1920


def test_timing_aggregate(tmp_path: Path):
    d = tmp_path / "job1"
    d.mkdir()
    (d / "timing_stats.json").write_text(
        '{"step_seconds": {"转写": 10, "__total__": 10}, "total_seconds": 10}',
        encoding="utf-8",
    )
    agg = aggregate_job_timings(tmp_path)
    assert agg["job_count"] >= 1


def test_rag_retrieve(tmp_path, monkeypatch):
    from src import rag_copy as rc
    monkeypatch.setattr(rc, "KNOWLEDGE_DIR", tmp_path)
    save_document("doc.md", "Spring Boot 微服务架构实战指南")
    ctx = retrieve_context("Spring Boot 项目", {"rag": {"enabled": True}}, top_k=1)
    assert "Spring" in ctx


def test_vertical_templates_list():
    assert any(t["id"] == "douyin" for t in list_vertical_templates())
