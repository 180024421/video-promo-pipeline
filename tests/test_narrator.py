from src.narrator import _fallback_segments


def test_fallback_segments_splits_long_text():
    segments = [{"start": 0.0, "end": 10.0, "text": "a" * 100}]
    out = _fallback_segments(segments, max_chars=40)
    assert len(out) >= 2
    assert all("text" in s for s in out)
