from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def suggest_clip_windows_by_beat(
    video_duration: float,
    cfg: dict[str, Any],
    clip_len: float = 75.0,
) -> list[tuple[float, float]] | None:
    """根据 BGM 节拍建议竖屏切片起点（需 librosa）。"""
    bcfg = (cfg.get("clip_short") or {}).get("bgm") or {}
    beat_cfg = cfg.get("bgm_beat") or {}
    if not beat_cfg.get("enabled", False):
        return None
    bgm = bcfg.get("file", "")
    if not bgm or not Path(bgm).exists():
        return None
    try:
        import librosa  # type: ignore
    except ImportError:
        console.print("[yellow]BGM 节拍对齐需 pip install librosa[/yellow]")
        return None

    y, sr = librosa.load(bgm, sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    if len(beat_times) < 2:
        return None

    windows: list[tuple[float, float]] = []
    count = int((cfg.get("clip_short") or {}).get("multi_clip_count", 1))
    step = max(1, len(beat_times) // max(count, 1))
    for i in range(0, len(beat_times), step):
        start = float(beat_times[i])
        if start + clip_len > video_duration:
            start = max(0.0, video_duration - clip_len)
        windows.append((start, clip_len))
        if len(windows) >= count:
            break
    console.print(f"[green]BGM 节拍[/green] tempo={float(tempo):.0f} → {len(windows)} 窗口")
    return windows
