"""流水线 DAG 可视化 + Webhook 触发。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PIPELINE_DAG: dict[str, list[str]] = {
    "preflight": [],
    "backup": ["preflight"],
    "auto_cut": ["backup"],
    "transcribe": ["backup"],
    "whisperx_align": ["transcribe"],
    "terminology": ["transcribe"],
    "chapter_export": ["terminology"],
    "smart_cut": ["transcribe"],
    "vision_cut": ["smart_cut"],
    "narration": ["transcribe"],
    "dubbing": ["narration"],
    "broll": ["auto_cut", "smart_cut"],
    "subtitle_burn": ["dubbing", "broll", "terminology"],
    "soft_export": ["dubbing", "terminology"],
    "i18n": ["dubbing"],
    "i18n_video": ["i18n"],
    "clip_short": ["subtitle_burn"],
    "cover": ["subtitle_burn"],
    "copy": ["transcribe", "terminology"],
    "video_qc": ["subtitle_burn", "clip_short"],
    "intro_outro": ["clip_short"],
    "pack": ["cover", "copy", "clip_short", "video_qc", "intro_outro"],
    "publish": ["pack"],
    "cloud_upload": ["publish"],
}

STEP_NAMES = {
    "preflight": "环境检查",
    "backup": "备份原片",
    "auto_cut": "粗剪去静音",
    "transcribe": "语音转写",
    "whisperx_align": "字级对齐",
    "terminology": "术语处理",
    "chapter_export": "章节导出",
    "smart_cut": "智能剪辑",
    "vision_cut": "视觉确认",
    "narration": "解说生成",
    "dubbing": "AI 配音",
    "broll": "B-roll 插入",
    "subtitle_burn": "硬字幕烧录",
    "soft_export": "软字幕导出",
    "i18n": "多语言翻译",
    "i18n_video": "多语言视频",
    "clip_short": "竖屏切片",
    "cover": "封面生成",
    "copy": "文案生成",
    "video_qc": "成品质检",
    "intro_outro": "片头片尾",
    "pack": "打包导出",
    "publish": "一键发布",
    "cloud_upload": "云存储上传",
}


def pipeline_dag_json() -> str:
    """返回 DAG JSON 供前端可视化。"""
    nodes = [{"id": k, "label": STEP_NAMES.get(k, k)} for k in PIPELINE_DAG]
    edges = []
    for step, deps in PIPELINE_DAG.items():
        for dep in deps:
            edges.append({"from": dep, "to": step})
    return json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)


def webhook_trigger(cfg: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """处理外部 Webhook 触发流水线。"""
    wh = cfg.get("webhook_trigger") or {}
    if not wh.get("enabled"):
        return {"ok": False, "detail": "Webhook 触发未启用"}
    secret = wh.get("secret", "")
    if secret and payload.get("secret") != secret:
        return {"ok": False, "detail": "密钥不匹配"}
    action = payload.get("action", "process")
    return {
        "ok": True,
        "action": action,
        "video_path": payload.get("video_path", ""),
        "preset": payload.get("preset", ""),
        "params": payload.get("params", {}),
    }
