from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from .auto_cut import run_auto_editor
from .clip_short import clip_vertical_short
from .config_loader import ROOT, load_config, output_dir
from .copywriter import generate_copy
from .cover import generate_cover
from .preflight import run_preflight
from .subtitle_burn import burn_subtitles
from .transcribe import build_chapter_outline, transcribe_video

console = Console()


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _find_work_video(out_dir: Path, stem: str) -> Path | None:
    for suffix in (".mp4", ".mkv", ".mov", ".webm"):
        cut = out_dir / f"{stem}_cut{suffix}"
        if cut.exists():
            return cut
    for p in out_dir.iterdir():
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".mov", ".webm"} and "_subtitled" not in p.stem:
            if "_short_" not in p.stem:
                return p
    return None


def _resolve_job_dir(
    video_path: Path,
    cfg: dict[str, Any],
    job_dir: Path | None,
) -> tuple[Path, str]:
    if job_dir:
        out = job_dir.resolve()
        out.mkdir(parents=True, exist_ok=True)
        return out, out.name
    job_name = f"{video_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return output_dir(cfg, job_name), job_name


def run_pipeline(
    video_path: Path,
    *,
    skip_cut: bool = False,
    skip_burn: bool = False,
    skip_copy: bool = False,
    only_transcribe: bool = False,
    only_copy: bool = False,
    config_path: Path | None = None,
    job_dir: Path | None = None,
    preflight: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    pcfg = cfg.get("pipeline") or {}
    resume = pcfg.get("resume", True) and not force

    if preflight:
        run_preflight(cfg, need_lm=not skip_copy and not only_transcribe)

    # --- 仅文案模式 ---
    if only_copy:
        if not job_dir:
            raise ValueError("only_copy 需要指定 job_dir")
        out_dir = job_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[bold]任务目录[/bold] {out_dir}")
        transcript_path = out_dir / "transcript.txt"
        if not transcript_path.exists():
            raise FileNotFoundError(f"缺少 transcript.txt: {transcript_path}")
        transcript = transcript_path.read_text(encoding="utf-8")
        seg_data = _load_json(out_dir / "segments.json")
        segments = (seg_data or {}).get("segments", []) if isinstance(seg_data, dict) else []
        chapter_outline = build_chapter_outline(segments) if segments else ""
        copy_data = generate_copy(transcript, cfg, out_dir, chapter_outline=chapter_outline)
        title_stem = out_dir.name.split("_")[0] if out_dir.name else "技术分享"
        cover_path = generate_cover(title_stem, cfg, out_dir, copy_data)
        return _write_summary(out_dir, None, None, None, None, copy_data, cover_path)

    video_path = video_path.resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"视频不存在: {video_path}")

    out_dir, _ = _resolve_job_dir(video_path, cfg, job_dir)
    console.print(f"[bold]任务目录[/bold] {out_dir}")

    # --- 原片备份 ---
    raw_copy = out_dir / video_path.name
    if pcfg.get("copy_source_video", False) or not resume:
        if not raw_copy.exists() or force:
            shutil.copy2(video_path, raw_copy)
    elif not raw_copy.exists():
        shutil.copy2(video_path, raw_copy)

    work_video = raw_copy
    cut_path: Path | None = None

    # --- 粗剪 ---
    if not skip_cut and not only_transcribe:
        existing = _find_work_video(out_dir, raw_copy.stem)
        if resume and existing and existing != raw_copy and "_cut" in existing.stem:
            work_video = existing
            cut_path = existing
            console.print(f"[yellow]续跑[/yellow] 使用已有粗剪 {existing.name}")
        else:
            cut_path = run_auto_editor(raw_copy, cfg, out_dir)
            if cut_path is not None:
                work_video = cut_path

    # --- 转写 ---
    segments_path = out_dir / "segments.json"
    tx: dict[str, Any]
    if resume and segments_path.exists() and not force:
        console.print("[yellow]续跑[/yellow] 跳过转写，使用已有 segments.json")
        seg_data = _load_json(segments_path) or {}
        segments = seg_data.get("segments", []) if isinstance(seg_data, dict) else []
        transcript = (out_dir / "transcript.txt").read_text(encoding="utf-8") if (out_dir / "transcript.txt").exists() else ""
        tx = {
            "srt_path": out_dir / "subtitle.srt",
            "transcript_path": out_dir / "transcript.txt",
            "segments_path": segments_path,
            "transcript": transcript,
            "segments": segments,
            "chapter_outline": build_chapter_outline(segments),
            "duration": seg_data.get("duration") if isinstance(seg_data, dict) else None,
            "subtitle_formats": {},
        }
    else:
        tx = transcribe_video(work_video, cfg, out_dir)

    if only_transcribe:
        return _write_summary(out_dir, raw_copy, work_video, work_video, tx, None, None)

    # --- 烧录字幕 ---
    final_video = work_video
    if not skip_burn:
        subtitled = out_dir / f"{work_video.stem}_subtitled{work_video.suffix}"
        if resume and subtitled.exists() and not force:
            final_video = subtitled
            console.print(f"[yellow]续跑[/yellow] 使用已有成片 {subtitled.name}")
        else:
            try:
                final_video = burn_subtitles(work_video, tx["srt_path"], cfg, out_dir)
            except RuntimeError as e:
                console.print(f"[yellow]{e}[/yellow]")

    # --- 竖屏切片 ---
    short_path: Path | None = None
    if not skip_burn:
        short_path = clip_vertical_short(final_video, tx.get("segments", []), cfg, out_dir)

    # --- 文案 ---
    copy_data = None
    if not skip_copy:
        promo_json = out_dir / "promo_copy.json"
        if resume and promo_json.exists() and not force:
            console.print("[yellow]续跑[/yellow] 跳过文案，使用已有 promo_copy.json")
            copy_data = _load_json(promo_json)
        else:
            copy_data = generate_copy(
                tx["transcript"],
                cfg,
                out_dir,
                chapter_outline=tx.get("chapter_outline", ""),
            )

    # --- 封面 ---
    cover_path = generate_cover(video_path.stem, cfg, out_dir, copy_data if isinstance(copy_data, dict) else None)

    return _write_summary(out_dir, raw_copy, work_video, final_video, tx, copy_data, cover_path, short_path, cut_path)


def _write_summary(
    out_dir: Path,
    raw_copy: Path | None,
    work_video: Path | None,
    final_video: Path | None,
    tx: dict[str, Any] | None,
    copy_data: Any,
    cover_path: Path | None,
    short_path: Path | None = None,
    cut_path: Path | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "job_dir": str(out_dir),
        "source_video": str(raw_copy) if raw_copy else None,
        "work_video": str(work_video) if work_video else None,
        "cut_video": str(cut_path) if cut_path else None,
        "final_video": str(final_video) if final_video else None,
        "short_video": str(short_path) if short_path else None,
        "cover": str(cover_path) if cover_path else None,
    }
    if tx:
        summary.update({
            "srt": str(tx.get("srt_path")),
            "transcript": str(tx.get("transcript_path")),
            "segments": str(tx.get("segments_path")),
            "subtitle_formats": tx.get("subtitle_formats"),
        })
    if copy_data:
        summary["promo_copy"] = str(out_dir / "promo_copy.md")
        summary["bilibili_description"] = str(out_dir / "bilibili_description.txt")
        summary["xiaohongshu_post"] = str(out_dir / "xiaohongshu_post.txt")

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"\n[bold green]全部完成[/bold green] 输出目录: {out_dir}")
    return summary
