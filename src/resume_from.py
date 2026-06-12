from __future__ import annotations

"""从指定步骤继续流水线。"""

STEP_ORDER = [
    "cut",
    "transcribe",
    "smart",
    "broll",
    "dub",
    "burn",
    "short",
    "copy",
    "cover",
    "pack",
]

STEP_TO_PIPELINE = {
    "cut": "粗剪",
    "transcribe": "转写",
    "smart": "智能剪辑",
    "broll": "B-roll",
    "dub": "配音解说",
    "burn": "烧录字幕",
    "short": "竖屏切片",
    "copy": "推广文案",
    "cover": "封面",
    "pack": "打包导出",
}


def step_index(step: str) -> int:
    try:
        return STEP_ORDER.index(step)
    except ValueError:
        return -1


def at_or_past(step_key: str, from_step: str | None) -> bool:
    if not from_step:
        return True
    a = step_index(step_key)
    b = step_index(from_step)
    if a < 0 or b < 0:
        return True
    return a >= b


def resolve_only_flags(from_step: str | None) -> dict[str, bool]:
    """将 from_step 映射为 only_* 标志（用于 Web 重跑）。"""
    if not from_step:
        return {}
    mapping = {
        "dub": "only_dub",
        "burn": "only_burn",
        "short": "only_short",
        "copy": "only_copy",
        "pack": "only_pack",
    }
    if from_step in mapping:
        return {mapping[from_step]: True}
    return {}


def suggest_resume_step(progress: dict | None) -> str | None:
    """根据 pipeline_progress 建议从哪步继续。"""
    if not progress:
        return None
    current = progress.get("current", "")
    if current == "完成":
        return None
    rev = {v: k for k, v in STEP_TO_PIPELINE.items()}
    return rev.get(current)
