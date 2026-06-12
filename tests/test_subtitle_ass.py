from src.subtitle_ass import segments_to_vtt, segments_to_ass


def test_vtt_and_ass():
    segs = [{"start": 1.0, "end": 2.5, "text": "测试字幕"}]
    vtt = segments_to_vtt(segs)
    assert vtt.startswith("WEBVTT")
    assert "测试字幕" in vtt
    ass = segments_to_ass(segs, {"subtitle": {"font_name": "Microsoft YaHei", "font_size": 22}})
    assert "[Events]" in ass
    assert "测试字幕" in ass
