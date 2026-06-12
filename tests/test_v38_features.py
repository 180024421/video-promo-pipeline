from __future__ import annotations

from pathlib import Path

from src.offline_mode import apply_offline_fallback
from src.template_market import list_market_templates, apply_market_template
from src.ab_feedback import record_feedback, suggest_from_feedback
from src.publish_preflight import run_publish_preflight
from src.whisper_prompt import build_whisper_initial_prompt


def test_offline_fallback():
    cfg = apply_offline_fallback({"offline": {"auto_fallback": True}, "lm_studio": {"enabled": True, "base_url": "http://127.0.0.1:9/v1"}})
    assert cfg.get("pipeline", {}).get("_offline") is True or "smart_cut" in cfg


def test_template_market():
    assert len(list_market_templates()) >= 3
    cfg = apply_market_template({}, "vertical_douyin")
    assert cfg["clip_short"]["vertical_template"] == "douyin"


def test_ab_feedback(tmp_path, monkeypatch):
    from src import ab_feedback as ab
    monkeypatch.setattr(ab, "FEEDBACK_FILE", tmp_path / "ab.json")
    record_feedback({"platform": "bilibili", "title": "A", "views": 100, "ctr": 0.05})
    record_feedback({"platform": "bilibili", "title": "B", "views": 200, "ctr": 0.08})
    s = suggest_from_feedback("bilibili")
    assert s.get("best_title") == "B"


def test_publish_preflight(tmp_path):
    d = tmp_path / "job"
    d.mkdir()
    (d / "summary.json").write_text('{"final_video": null}', encoding="utf-8")
    r = run_publish_preflight(d, {"publish_preflight": {"enabled": True, "require_cover": False}})
    assert "checks" in r


def test_hotwords_in_prompt():
    p = build_whisper_initial_prompt({"whisper": {"hotwords": ["JetLinks"], "hotwords_from_terminology": False}})
    assert "JetLinks" in p
