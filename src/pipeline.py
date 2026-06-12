from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

from .auto_cut import run_auto_editor
from .broll import apply_broll, detect_broll_markers
from .clip_short import clip_vertical_short
from .config_loader import load_config, output_dir
from .copywriter import generate_copy
from .cover import generate_cover
from .cover_ab import generate_cover_variants
from .dubbing import run_dubbing
from .export_pack import pack_job_zip
from .gpu_scheduler import after_whisper, run_lm_step
from .hot_topics import inject_hot_topics
from .i18n_video import export_i18n_subtitle_track
from .intro_outro import apply_intro_outro
from .job_logger import get_job_logger, log_job
from .i18n import translate_narration
from .resume_from import at_or_past, resolve_only_flags
from .sensitive_scan import scan_copy_sensitive
from .narrator import generate_narration
from .presets import apply_preset
from .preflight import run_preflight
from .progress_tracker import PIPELINE_STEPS, ProgressTracker
from .plugins import run_plugins
from .publish import run_publish
from .publish_pack import build_publish_pack
from .smart_cut import apply_clip_plan, generate_clip_plan
from .soft_export import export_soft_subtitle_package
from .subtitle_burn import burn_subtitles
from .transcribe import build_chapter_outline, transcribe_video
from .vision_cut import enhance_clip_plan_with_vision
from .whisperx_align import align_segments_whisperx

console = Console()

StepCallback = Callable[[str], None] | None

STEPS = PIPELINE_STEPS


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _step(on_step: StepCallback, name: str, tracker: ProgressTracker | None = None) -> None:
    if tracker:
        tracker.tick(name)
    elif on_step:
        on_step(name)
    console.print(f"[bold cyan]▶ {name}[/bold cyan]")


def _find_work_video(out_dir: Path, stem: str) -> Path | None:
    for suffix in (".mp4", ".mkv", ".mov", ".webm"):
        for tag in ("_cut", "_smart", "_broll", "_dubbed"):
            p = out_dir / f"{stem}{tag}{suffix}"
            if p.exists():
                return p
    for p in out_dir.iterdir():
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".mov", ".webm"}:
            if "_subtitled" not in p.stem and "_short_" not in p.stem and "_raw" not in p.stem:
                return p
    return None


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _resolve_cfg(
    config_path: Path | None,
    preset: str | None = None,
    cfg_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    pid = preset or (cfg.get("workflow") or {}).get("preset")
    if pid:
        cfg = apply_preset(cfg, pid)
    if cfg_override:
        cfg = _deep_merge(cfg, cfg_override)
    return cfg


def run_pipeline(
    video_path: Path,
    *,
    skip_cut: bool = False,
    skip_burn: bool = False,
    skip_copy: bool = False,
    skip_dub: bool = False,
    only_transcribe: bool = False,
    only_copy: bool = False,
    only_dub: bool = False,
    only_burn: bool = False,
    only_short: bool = False,
    only_pack: bool = False,
    config_path: Path | None = None,
    job_dir: Path | None = None,
    preflight: bool = False,
    force: bool = False,
    from_step: str | None = None,
    preset: str | None = None,
    cfg_override: dict[str, Any] | None = None,
    on_step: StepCallback = None,
) -> dict[str, Any]:
    cfg = _resolve_cfg(config_path, preset, cfg_override)
    pcfg = cfg.get("pipeline") or {}
    if from_step:
        only_flags = resolve_only_flags(from_step)
        only_dub = only_dub or only_flags.get("only_dub", False)
        only_burn = only_burn or only_flags.get("only_burn", False)
        only_short = only_short or only_flags.get("only_short", False)
        only_copy = only_copy or only_flags.get("only_copy", False)
        only_pack = only_pack or only_flags.get("only_pack", False)
        force = True
    resume = pcfg.get("resume", True) and not force

    if preflight:
        run_preflight(cfg, need_lm=not skip_copy and not only_transcribe)

    # --- 仅文案 ---
    if only_copy:
        if not job_dir:
            raise ValueError("only_copy 需要 job_dir")
        out_dir = job_dir.resolve()
        _step(on_step, "推广文案")
        transcript = (out_dir / "transcript.txt").read_text(encoding="utf-8")
        seg_data = _load_json(out_dir / "segments.json") or {}
        segments = seg_data.get("segments", []) if isinstance(seg_data, dict) else []
        copy_data = generate_copy(transcript, cfg, out_dir, chapter_outline=build_chapter_outline(segments), segments=segments)
        vid = next((p for p in out_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv", ".mov"}), None)
        cover_path = generate_cover(out_dir.name.split("_")[0], cfg, out_dir, copy_data, source_video=vid)
        return _write_summary(out_dir, None, None, None, None, copy_data, cover_path, on_step=on_step)

    # --- 仅打包 ---
    if only_pack:
        if not job_dir:
            raise ValueError("only_pack 需要 job_dir")
        out_dir = job_dir.resolve()
        _step(on_step, "打包导出")
        zip_path = pack_job_zip(out_dir, cfg)
        pub = run_publish(out_dir, cfg)
        return {"job_dir": str(out_dir), "zip": str(zip_path) if zip_path else None, "publish": pub}

    video_path = video_path.resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"视频不存在: {video_path}")

    if job_dir:
        out_dir = job_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = output_dir(cfg, f"{video_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    tracker = ProgressTracker(out_dir, on_step)
    jlog = get_job_logger(out_dir, out_dir.name)
    log_job(out_dir, f"开始流水线 from_step={from_step or 'full'}")

    def _tick(name: str) -> None:
        _step(None, name, tracker)
        log_job(out_dir, name)

    raw_copy = out_dir / video_path.name
    if not raw_copy.exists() or force:
        _tick("备份原片")
        shutil.copy2(video_path, raw_copy)

    work_video = raw_copy
    cut_path: Path | None = None
    tx: dict[str, Any] | None = None

    # --- 部分重跑：仅配音/烧录/竖屏 ---
    if only_dub or only_burn or only_short:
        seg_data = _load_json(out_dir / "segments.json") or {}
        segments = seg_data.get("segments", []) if isinstance(seg_data, dict) else []
        transcript = (out_dir / "transcript.txt").read_text(encoding="utf-8") if (out_dir / "transcript.txt").exists() else ""
        tx = {
            "srt_path": out_dir / "subtitle.srt",
            "transcript": transcript,
            "segments": segments,
            "chapter_outline": build_chapter_outline(segments),
        }
        for p in out_dir.iterdir():
            if p.suffix.lower() in {".mp4", ".mkv"} and "_subtitled" not in p.stem and "_short_" not in p.stem:
                work_video = p
                break

    # --- 粗剪 ---
    if not skip_cut and not only_transcribe and not only_dub and not only_burn and not only_short and at_or_past("cut", from_step):
        _tick("粗剪")
        existing = _find_work_video(out_dir, raw_copy.stem)
        if resume and existing and "_cut" in existing.stem and not force:
            work_video = existing
            cut_path = existing
        else:
            cut_path = run_auto_editor(raw_copy, cfg, out_dir)
            if cut_path:
                work_video = cut_path

    # --- 转写 ---
    if tx is None:
        segments_path = out_dir / "segments.json"
        if (only_dub or only_burn or only_short) and segments_path.exists():
            seg_data = _load_json(segments_path) or {}
            segments = seg_data.get("segments", []) if isinstance(seg_data, dict) else []
            transcript = (out_dir / "transcript.txt").read_text(encoding="utf-8")
            tx = {"srt_path": out_dir / "subtitle.srt", "transcript": transcript, "segments": segments,
                  "chapter_outline": build_chapter_outline(segments), "transcript_path": out_dir / "transcript.txt",
                  "segments_path": segments_path}
        elif resume and segments_path.exists() and not force and not only_transcribe and at_or_past("transcribe", from_step):
            seg_data = _load_json(segments_path) or {}
            segments = seg_data.get("segments", []) if isinstance(seg_data, dict) else []
            transcript = (out_dir / "transcript.txt").read_text(encoding="utf-8")
            tx = {"srt_path": out_dir / "subtitle.srt", "transcript": transcript, "segments": segments,
                  "chapter_outline": build_chapter_outline(segments), "transcript_path": out_dir / "transcript.txt",
                  "segments_path": segments_path}
        else:
            if at_or_past("transcribe", from_step):
                _tick("转写")
                tx = transcribe_video(work_video, cfg, out_dir)
                after_whisper(cfg)
                if (cfg.get("whisperx") or {}).get("enabled", False):
                    tx["segments"] = align_segments_whisperx(work_video, tx.get("segments", []), cfg)
                    (out_dir / "segments.json").write_text(
                        json.dumps({"segments": tx["segments"]}, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                run_plugins("after_transcribe", {"job_dir": out_dir, "tx": tx}, cfg)
            else:
                raise RuntimeError(f"无法从步骤 {from_step} 继续：缺少转写结果")

    assert tx is not None

    if only_transcribe:
        tracker.done()
        return _write_summary(out_dir, raw_copy, work_video, work_video, tx, None, None, on_step=on_step, tracker=tracker)

    # --- 智能剪辑 ---
    smart_cfg = cfg.get("smart_cut") or {}
    if smart_cfg.get("enabled", False) and not only_dub and not only_burn and not only_short and at_or_past("smart", from_step):
        _tick("智能剪辑")
        smart_path = out_dir / f"{work_video.stem}_smart{work_video.suffix}"
        if resume and smart_path.exists() and not force:
            work_video = smart_path
        else:
            clips = run_lm_step(cfg, lambda: generate_clip_plan(tx["transcript"], tx["segments"], cfg, out_dir))
            if (cfg.get("vision") or {}).get("enabled", False):
                _tick("视觉分析")
                vclips = enhance_clip_plan_with_vision(work_video, tx["transcript"], tx["segments"], cfg, out_dir)
                if vclips:
                    clips = vclips
            smart = apply_clip_plan(work_video, clips, cfg, out_dir)
            if smart:
                work_video = smart

    # --- B-roll ---
    broll_cfg = cfg.get("broll") or {}
    if broll_cfg.get("enabled", False) and not only_dub and not only_burn and not only_short and at_or_past("broll", from_step):
        _tick("B-roll")
        markers = detect_broll_markers(tx["transcript"], tx["segments"], cfg, out_dir)
        broll_vid = apply_broll(work_video, markers, cfg, out_dir)
        if broll_vid:
            work_video = broll_vid

    # --- 配音 ---
    ncfg = cfg.get("narration") or {}
    dub_meta: dict[str, Any] | None = None
    subtitle_srt = tx["srt_path"]
    narration: dict[str, Any] | None = None

    if not skip_dub and ncfg.get("enabled", False) and not only_burn and not only_short and at_or_past("dub", from_step):
        _tick("配音解说")
        narr_path = out_dir / "narration.json"
        if resume and narr_path.exists() and not force and not only_dub:
            narration = json.loads(narr_path.read_text(encoding="utf-8"))
        else:
            narration = run_lm_step(cfg, lambda: generate_narration(tx["transcript"], tx["segments"], cfg, out_dir))

        if (cfg.get("i18n") or {}).get("enabled", False):
            _tick("多语言")
            narration = translate_narration(narration, cfg, out_dir)

        dub_json = out_dir / "dubbing.json"
        if resume and dub_json.exists() and not force and not only_dub:
            dub_meta = json.loads(dub_json.read_text(encoding="utf-8"))
            dubbed = Path(dub_meta.get("dubbed_video", ""))
            if dubbed.exists():
                work_video = dubbed
        else:
            dub_meta = run_dubbing(work_video, narration, cfg, out_dir)
            if dub_meta.get("enabled") and dub_meta.get("dubbed_video"):
                work_video = Path(dub_meta["dubbed_video"])
        if (cfg.get("dubbing") or {}).get("burn_narration_subtitles", True) and (out_dir / "narration.srt").exists():
            subtitle_srt = out_dir / "narration.srt"

    if only_dub:
        tracker.done()
        return _write_summary(out_dir, raw_copy, work_video, work_video, tx, None, None, dub_meta=dub_meta, on_step=on_step, tracker=tracker)

    # --- 烧录字幕 / 软字幕 ---
    final_video = work_video
    pcfg = cfg.get("pipeline") or {}
    subtitle_mode = pcfg.get("subtitle_mode", "burn")
    if not skip_burn and not only_short and at_or_past("burn", from_step):
        if subtitle_mode == "soft":
            _tick("软字幕导出")
            export_soft_subtitle_package(work_video, subtitle_srt, out_dir, cfg)
            final_video = work_video
        else:
            _tick("烧录字幕")
            subtitled = out_dir / f"{work_video.stem}_subtitled{work_video.suffix}"
            if resume and subtitled.exists() and not force and not only_burn:
                final_video = subtitled
            else:
                try:
                    final_video = burn_subtitles(work_video, subtitle_srt, cfg, out_dir)
                except RuntimeError as e:
                    console.print(f"[yellow]{e}[/yellow]")

    if only_burn:
        tracker.done()
        return _write_summary(out_dir, raw_copy, work_video, final_video, tx, None, None, dub_meta=dub_meta, on_step=on_step, tracker=tracker)

    # --- 竖屏 ---
    short_path: Path | None = None
    if (not skip_burn or only_short) and at_or_past("short", from_step):
        short_path = clip_vertical_short(
            final_video if not only_short else work_video,
            tx.get("segments", []),
            cfg,
            out_dir,
            transcript=tx.get("transcript", ""),
            subtitle_srt=subtitle_srt if isinstance(subtitle_srt, Path) else Path(subtitle_srt),
            on_step=on_step,
        )

    if only_short:
        tracker.done()
        return _write_summary(out_dir, raw_copy, work_video, final_video, tx, None, None, short_path, cut_path, dub_meta, on_step=on_step, tracker=tracker)

    copy_data = None
    if not skip_copy and at_or_past("copy", from_step):
        _tick("推广文案")
        run_plugins("before_copy", {"job_dir": out_dir, "tx": tx}, cfg)
        promo_json = out_dir / "promo_copy.json"
        hot = inject_hot_topics(cfg, tx.get("transcript", ""))
        if hot:
            tx = {**tx, "hot_topics": hot}
        if resume and promo_json.exists() and not force:
            copy_data = _load_json(promo_json)
        else:
            copy_data = run_lm_step(cfg, lambda: generate_copy(
                tx["transcript"], cfg, out_dir, chapter_outline=tx.get("chapter_outline", ""),
                segments=tx.get("segments", []),
            ))
        if copy_data:
            scan = scan_copy_sensitive(copy_data, cfg)
            (out_dir / "sensitive_scan.json").write_text(json.dumps(scan, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- 封面 ---
    if at_or_past("cover", from_step):
        _tick("封面")
        cover_src = final_video if final_video and Path(str(final_video)).exists() else work_video
        ccfg = cfg.get("cover") or {}
        if ccfg.get("ab_enabled", False):
            cover_paths = generate_cover_variants(
                video_path.stem, cfg, out_dir,
                copy_data if isinstance(copy_data, dict) else None,
                source_video=cover_src,
            )
            cover_path = cover_paths[0] if cover_paths else None
        else:
            cover_path = generate_cover(
                video_path.stem, cfg, out_dir,
                copy_data if isinstance(copy_data, dict) else None,
                source_video=cover_src,
            )
    else:
        cover_path = None

    # --- 片头片尾 ---
    if at_or_past("pack", from_step) and final_video:
        branded = apply_intro_outro(Path(str(final_video)), cfg, out_dir)
        if branded != final_video:
            final_video = branded

    # --- 多语言成片 ---
    export_i18n_subtitle_track(out_dir, cfg)

    # --- 打包 ---
    zip_path = None
    pub = None
    if at_or_past("pack", from_step):
        _tick("打包导出")
        zip_path = pack_job_zip(out_dir, cfg)
        _tick("发布")
        pub = run_publish(out_dir, cfg)
        build_publish_pack(out_dir, cfg)

    summary = _write_summary(
        out_dir, raw_copy, work_video, final_video, tx, copy_data, cover_path,
        short_path, cut_path, dub_meta, on_step=on_step, tracker=tracker,
    )
    run_plugins("after_pack", {"job_dir": out_dir, "summary": summary}, cfg)
    if zip_path:
        summary["zip"] = str(zip_path)
    if pub:
        summary["publish"] = pub
    return summary


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
    dub_meta: dict[str, Any] | None = None,
    on_step: StepCallback = None,
    tracker: ProgressTracker | None = None,
) -> dict[str, Any]:
    if tracker:
        tracker.done()
    elif on_step:
        on_step("完成")
    summary: dict[str, Any] = {
        "job_dir": str(out_dir),
        "source_video": str(raw_copy) if raw_copy else None,
        "work_video": str(work_video) if work_video else None,
        "cut_video": str(cut_path) if cut_path else None,
        "final_video": str(final_video) if final_video else None,
        "short_video": str(short_path) if short_path else None,
        "cover": str(cover_path) if cover_path else None,
        "steps": STEPS,
    }
    if tx:
        summary.update({
            "srt": str(tx.get("srt_path")),
            "transcript": str(tx.get("transcript_path", out_dir / "transcript.txt")),
            "segments": str(tx.get("segments_path", out_dir / "segments.json")),
        })
    if copy_data:
        summary["promo_copy"] = str(out_dir / "promo_copy.md")
    if dub_meta:
        summary["dubbing"] = dub_meta

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"\n[bold green]全部完成[/bold green] {out_dir}")
    return summary
