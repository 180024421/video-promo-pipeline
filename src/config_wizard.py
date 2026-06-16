"""配置向导：Web 端引导式表单。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config_loader import ROOT, save_config


def build_wizard_template() -> dict[str, Any]:
    """返回向导问题列表。"""
    return {
        "steps": [
            {"id": "whisper", "question": "Whisper 模型大小？", "options": ["tiny", "small", "medium", "large-v2"], "default": "small", "key": "whisper.model"},
            {"id": "device", "question": "使用 GPU 加速？", "options": ["cuda", "cpu"], "default": "cuda", "key": "whisper.device"},
            {"id": "preset", "question": "工作流预设？", "options": ["", "tech_tutorial", "short_commentary", "game_commentary"], "default": "", "key": "workflow.preset"},
            {"id": "quality", "question": "成片质量？", "options": ["fast", "balanced", "quality"], "default": "balanced", "key": "video_quality.preset"},
            {"id": "encoder", "question": "视频编码器？", "options": ["libx264", "h264_nvenc"], "default": "libx264", "key": "video_quality.encoder"},
        ],
    }


def apply_wizard_answers(cfg: dict[str, Any], answers: dict[str, str]) -> dict[str, Any]:
    """将向导答案写回配置。"""
    result = dict(cfg)
    for key_path, value in answers.items():
        keys = key_path.split(".")
        target = result
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value
    return result
