#!/usr/bin/env python3
"""本地录屏视频处理：字幕 + 粗剪 + 烧录 + LM Studio 文案。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.config_loader import load_config
from src.pipeline import run_pipeline
from src.preflight import run_preflight


def _merge_runtime_config(cfg: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """将 CLI 参数覆盖到配置中。"""
    copy_cfg = cfg.setdefault("copy", {})
    if args.persona:
        for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
            if p in copy_cfg:
                copy_cfg[p]["persona"] = args.persona
        if "persona" not in copy_cfg:
            copy_cfg["persona"] = args.persona
    if args.topic:
        for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
            if p in copy_cfg:
                copy_cfg[p]["content_type"] = args.topic
        if "topic" not in copy_cfg:
            copy_cfg["topic"] = args.topic
    if args.style:
        for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
            if p in copy_cfg:
                copy_cfg[p]["style"] = args.style
    if args.tone:
        for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
            if p in copy_cfg:
                copy_cfg[p]["tone"] = args.tone
    if args.keywords:
        kw = [k.strip() for k in args.keywords.split(",")]
        for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
            if p in copy_cfg:
                copy_cfg[p]["keywords"] = kw
        if "keywords" not in copy_cfg:
            copy_cfg["keywords"] = kw
    if args.forbidden:
        fb = [w.strip() for w in args.forbidden.split(",")]
        gen = copy_cfg.setdefault("general", {})
        gen.setdefault("global_forbidden_words", []).extend(fb)
    if args.platforms:
        enabled = [p.strip().lower() for p in args.platforms.split(",")]
        for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
            if p in copy_cfg:
                copy_cfg[p]["enabled"] = p in enabled
    if args.only_platform:
        enabled = [p.strip().lower() for p in args.only_platform.split(",")]
        for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
            if p in copy_cfg:
                copy_cfg[p]["enabled"] = p in enabled
    if args.hook_style:
        gen = copy_cfg.setdefault("general", {})
        gen["short_hook_style"] = args.hook_style
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(description="本地视频推广流水线 v2")
    parser.add_argument("video", type=Path, nargs="?", help="录制的视频文件路径 (.mp4/.mkv)")
    parser.add_argument("--config", type=Path, default=None, help="配置文件路径，默认 config.yaml")
    parser.add_argument("--job-dir", type=Path, default=None, help="指定/续跑任务输出目录")
    parser.add_argument("--skip-cut", action="store_true", help="跳过 Auto-Editor 粗剪")
    parser.add_argument("--skip-burn", action="store_true", help="跳过 FFmpeg 烧录字幕")
    parser.add_argument("--skip-copy", action="store_true", help="跳过 LM Studio 文案生成")
    parser.add_argument("--skip-dub", action="store_true", help="跳过 AI 配音解说")
    parser.add_argument("--only-transcribe", action="store_true", help="仅转写字幕")
    parser.add_argument("--only-copy", action="store_true", help="仅根据已有 transcript 生成文案")
    parser.add_argument("--only-dub", action="store_true", help="仅重跑配音（需已有转写）")
    parser.add_argument("--only-burn", action="store_true", help="仅重跑烧录字幕")
    parser.add_argument("--only-short", action="store_true", help="仅重跑竖屏切片")
    parser.add_argument("--only-pack", action="store_true", help="仅打包 zip + 发布 manifest")
    parser.add_argument("--preset", default="", help="工作流预设 tech_tutorial|short_commentary|game_commentary")
    parser.add_argument("--preflight", action="store_true", help="运行前检查环境")
    parser.add_argument("--force", action="store_true", help="忽略断点续跑，强制重新执行")

    # 运行时文案覆盖
    parser.add_argument("--persona", default="", help="覆盖文案人设")
    parser.add_argument("--topic", default="", help="覆盖主题/内容定位")
    parser.add_argument("--style", default="", help="覆盖风格")
    parser.add_argument("--tone", default="", help="覆盖语气")
    parser.add_argument("--keywords", default="", help="覆盖关键词，逗号分隔")
    parser.add_argument("--forbidden", default="", help="追加禁用词，逗号分隔")
    parser.add_argument("--platforms", default="", help="启用哪些平台，逗号分隔如 bilibili,xiaohongshu")
    parser.add_argument("--only-platform", default="", help="仅生成指定平台文案")
    parser.add_argument("--hook-style", default="", help="钩子风格：痛点反问式|结果前置式|悬念式|数字式|对比式")
    args = parser.parse_args()

    cfg = load_config(args.config)
    cfg = _merge_runtime_config(cfg, args)

    if args.only_copy:
        if not args.job_dir:
            parser.error("--only-copy 需要配合 --job-dir")
        run_pipeline(args.job_dir, only_copy=True, job_dir=args.job_dir, preflight=args.preflight, preset=args.preset or None)
        return

    if args.only_pack:
        if not args.job_dir:
            parser.error("--only-pack 需要 --job-dir")
        run_pipeline(args.job_dir, only_pack=True, job_dir=args.job_dir, preflight=args.preflight)
        return

    if args.only_dub or args.only_burn or args.only_short:
        if not args.job_dir:
            parser.error("分步重跑需要 --job-dir")
        run_pipeline(
            args.job_dir,
            only_dub=args.only_dub,
            only_burn=args.only_burn,
            only_short=args.only_short,
            job_dir=args.job_dir,
            preflight=args.preflight,
            force=args.force,
            preset=args.preset or None,
        )
        return

    if args.preflight and not args.video:
        ok = run_preflight(cfg)
        raise SystemExit(0 if ok else 1)

    if not args.video:
        parser.error("请提供 video 路径，或使用 --preflight / --only-copy")

    run_pipeline(
        args.video,
        skip_cut=args.skip_cut,
        skip_burn=args.skip_burn,
        skip_copy=args.skip_copy,
        skip_dub=args.skip_dub,
        only_transcribe=args.only_transcribe,
        config_path=args.config,
        job_dir=args.job_dir,
        preflight=args.preflight,
        force=args.force,
        preset=args.preset or None,
    )


if __name__ == "__main__":
    main()
