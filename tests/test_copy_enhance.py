from src.chapters import build_chapters_from_segments
from src.copy_enhance import deduplicate_titles, post_process_copy, score_titles


def test_deduplicate_titles():
    titles = ["Java 教程", "Java教程", "Spring Boot 实战", "完全不同的标题"]
    out = deduplicate_titles(titles, threshold=0.75)
    assert len(out) < len(titles)
    assert "Spring Boot 实战" in out


def test_chapters():
    segs = [
        {"start": 0, "end": 40, "text": "开场介绍"},
        {"start": 40, "end": 90, "text": "第一章内容"},
        {"start": 90, "end": 200, "text": "第二章深入"},
    ]
    cfg = {"copy": {"bilibili": {"chapters_enabled": True}, "general": {"max_chapters": 5, "min_chapter_duration": 30}}}
    ch = build_chapters_from_segments(segs, cfg)
    assert len(ch) >= 1
    assert "time" in ch[0]


def test_post_process_copy():
    data = {"bilibili": {"titles": ["Java 教程", "Java教程", "Spring 实战"]}}
    cfg = {"copy": {"general": {"deduplicate_titles": True, "consistency_check": True, "title_scoring_enabled": True}}}
    out = post_process_copy(data, cfg, "这是一段关于 Java 和 Spring 的教程转写")
    assert len(out["bilibili"]["titles"]) <= 3
