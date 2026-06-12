from __future__ import annotations

from typing import Any

BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "tech_tutorial_v2",
        "name": "技术教程（干货）",
        "category": "prompt",
        "platform": "bilibili",
        "data": {
            "name": "技术教程干货",
            "platform": "bilibili",
            "persona": "资深工程师",
            "style": "步骤清晰、少废话",
            "system_prompt": "你是 B 站科技区 UP 主，输出可跟做的教程文案。",
        },
    },
    {
        "id": "short_hook_v2",
        "name": "短视频钩子型",
        "category": "prompt",
        "platform": "douyin",
        "data": {
            "name": "抖音钩子",
            "platform": "douyin",
            "persona": "快节奏解说",
            "style": "前三秒强钩子",
        },
    },
    {
        "id": "vertical_douyin",
        "name": "抖音竖屏安全区",
        "category": "vertical",
        "platform": "douyin",
        "clip_short": {"vertical_template": "douyin"},
    },
    {
        "id": "vertical_xhs",
        "name": "小红书竖屏",
        "category": "vertical",
        "platform": "xiaohongshu",
        "clip_short": {"vertical_template": "xiaohongshu"},
    },
    {
        "id": "workflow_offline",
        "name": "离线模式（仅转写+粗剪+字幕）",
        "category": "workflow",
        "pipeline": {"subtitle_mode": "burn"},
        "offline": {"auto_fallback": True},
        "lm_studio": {"enabled": False},
        "smart_cut": {"enabled": False},
        "narration": {"enabled": False},
    },
]


def list_market_templates(category: str = "") -> list[dict[str, Any]]:
    if category:
        return [t for t in BUILTIN_TEMPLATES if t.get("category") == category]
    return list(BUILTIN_TEMPLATES)


def apply_market_template(cfg: dict[str, Any], template_id: str) -> dict[str, Any]:
    tpl = next((t for t in BUILTIN_TEMPLATES if t["id"] == template_id), None)
    if not tpl:
        return cfg
    out = dict(cfg)
    if tpl.get("category") == "prompt" and "data" in tpl:
        from .prompt_templates import save_template
        save_template(template_id, tpl["data"])
    for key in ("clip_short", "pipeline", "offline", "lm_studio", "smart_cut", "narration"):
        if key in tpl and isinstance(tpl[key], dict):
            out[key] = {**(out.get(key) or {}), **tpl[key]}
    return out
