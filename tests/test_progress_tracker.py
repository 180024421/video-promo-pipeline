from pathlib import Path

from src.progress_tracker import ProgressTracker, load_progress


def test_progress_tracker(tmp_path: Path):
    steps_seen: list[str] = []

    def on_step(s: str):
        steps_seen.append(s)

    tracker = ProgressTracker(tmp_path, on_step)
    tracker.tick("备份原片")
    tracker.tick("转写")
    tracker.done()

    data = load_progress(tmp_path)
    assert data is not None
    assert "备份原片" in data["completed"]
    assert data["current"] == "完成"
    assert data["progress"] == 100
    assert steps_seen == ["备份原片", "转写", "完成"]
