from pathlib import Path

from src.chapters import build_chapters_from_segments
from src.copy_enhance import deduplicate_titles
from src.lm_usage import load_stats, record_usage
from src.plugins import run_plugins
from src.speaker_diarize import _heuristic_diarize


def test_lm_usage_record():
    record_usage(model="test", prompt_tokens=10, completion_tokens=20, label="test")
    s = load_stats()
    assert s["total_calls"] >= 1


def test_heuristic_diarize():
    segs = [
        {"start": 0, "end": 2, "text": "a"},
        {"start": 5, "end": 7, "text": "b"},
    ]
    out = _heuristic_diarize(segs, {"diarization": {"speaker_gap_sec": 1.5}})
    assert out[0]["speaker"] != out[1]["speaker"]


def test_plugins_noop():
    run_plugins("after_transcribe", {"job_dir": Path(".")}, {"pipeline": {"plugins": {}}})


def test_deduplicate():
    assert len(deduplicate_titles(["A", "A", "B"], 0.99)) == 2
