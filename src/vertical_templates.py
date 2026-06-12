from __future__ import annotations

from typing import Any

PLATFORM_PRESETS: dict[str, dict[str, Any]] = {
    "douyin": {
        "width": 1080,
        "height": 1920,
        "safe_margin_top": 140,
        "safe_margin_bottom": 280,
        "caption_style": {"position": "bottom", "margin_v": 320},
    },
    "xiaohongshu": {
        "width": 1080,
        "height": 1440,
        "safe_margin_top": 100,
        "safe_margin_bottom": 200,
        "caption_style": {"position": "bottom", "margin_v": 240},
    },
    "weixin_channels": {
        "width": 1080,
        "height": 1920,
        "safe_margin_top": 120,
        "safe_margin_bottom": 260,
        "caption_style": {"position": "bottom", "margin_v": 300},
    },
    "bilibili_vertical": {
        "width": 1080,
        "height": 1920,
        "safe_margin_top": 100,
        "safe_margin_bottom": 200,
        "caption_style": {"position": "bottom", "margin_v": 200},
    },
}


def apply_vertical_template(cfg: dict[str, Any], platform: str | None = None) -> dict[str, Any]:
    """将平台竖屏安全区预设合并进 clip_short 配置。"""
    out = dict(cfg)
    ccfg = dict(out.get("clip_short") or {})
    tpl_name = platform or ccfg.get("vertical_template") or (out.get("clip_short") or {}).get("platform", "")
    preset = PLATFORM_PRESETS.get(tpl_name or "")
    if not preset:
        return out
    for k, v in preset.items():
        if k == "caption_style" and isinstance(v, dict):
            cstyle = dict(ccfg.get("caption_style") or {})
            cstyle.update(v)
            ccfg["caption_style"] = cstyle
        else:
            ccfg[k] = v
    ccfg["vertical_template"] = tpl_name
    out["clip_short"] = ccfg
    return out


def list_vertical_templates() -> list[dict[str, str]]:
    return [{"id": k, "name": k, "size": f"{v.get('width')}x{v.get('height')}"} for k, v in PLATFORM_PRESETS.items()]
