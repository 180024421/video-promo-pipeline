from src.subtitle_post import post_process_segments
from src.transcribe import segments_to_srt, build_chapter_outline


def test_segments_to_srt():
    segs = [
        {"start": 0.0, "end": 1.5, "text": "你好"},
        {"start": 2.0, "end": 4.0, "text": "世界"},
    ]
    srt = segments_to_srt(segs)
    assert "00:00:00,000 --> 00:00:01,500" in srt
    assert "你好" in srt
    assert "2\n" in srt or srt.startswith("1\n")


def test_post_process_merge_short():
    segs = [
        {"start": 0, "end": 0.5, "text": "短"},
        {"start": 0.5, "end": 1.0, "text": "句"},
    ]
    cfg = {"subtitle": {"merge_min_duration": 1.2, "max_chars_per_line": 18, "remove_fillers": False}}
    out = post_process_segments(segs, cfg)
    assert len(out) == 1
    assert "短" in out[0]["text"] and "句" in out[0]["text"]


def test_chapter_outline():
    segs = [{"start": i * 10, "end": i * 10 + 5, "text": f"seg{i}"} for i in range(20)]
    outline = build_chapter_outline(segs, max_items=5)
    lines = [l for l in outline.splitlines() if l.strip()]
    assert 1 <= len(lines) <= 5
