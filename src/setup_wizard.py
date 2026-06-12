from __future__ import annotations

import shutil
from typing import Any

from .config_loader import ROOT, load_config
from .ffmpeg_installer import is_ffmpeg_ready
from .optional_deps import check_optional
from .service_checks import check_lm_studio_detail


def get_setup_checklist(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    steps: list[dict[str, Any]] = []

    ff_ok = is_ffmpeg_ready(cfg)
    steps.append({
        "id": "ffmpeg",
        "title": "安装 FFmpeg",
        "ok": ff_ok,
        "hint": "仪表盘可一键安装到 tools/ffmpeg/",
        "action": "install_ffmpeg",
    })

    wh_ok = False
    try:
        import faster_whisper  # noqa: F401
        wh_ok = True
    except ImportError:
        pass
    steps.append({
        "id": "whisper",
        "title": "安装 faster-whisper",
        "ok": wh_ok,
        "hint": "运行 .\\run.ps1 -Setup",
        "action": "setup",
    })

    lm = check_lm_studio_detail(cfg)
    steps.append({
        "id": "lm_studio",
        "title": "启动 LM Studio",
        "ok": lm.get("ok", False),
        "hint": "加载模型并开启 Local Server (1234)",
        "action": "open_lm",
    })

    cfg_path = ROOT / "config.yaml"
    steps.append({
        "id": "config",
        "title": "生成 config.yaml",
        "ok": cfg_path.exists(),
        "hint": "复制 config.example.yaml",
        "action": "setup",
    })

    opt = check_optional()
    steps.append({
        "id": "optional",
        "title": "可选增强依赖",
        "ok": any(opt.values()),
        "hint": f"已装: {', '.join(k for k, v in opt.items() if v) or '无'}",
        "action": "install_optional",
        "optional": opt,
    })

    done = sum(1 for s in steps if s["ok"])
    return {
        "ready": ff_ok and wh_ok and lm.get("ok", False),
        "progress": f"{done}/{len(steps)}",
        "steps": steps,
    }
