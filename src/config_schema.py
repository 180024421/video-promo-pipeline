from __future__ import annotations

from typing import Any

REQUIRED_SECTIONS = ("whisper", "web", "output")
KNOWN_SECTIONS = {
    "whisper", "auto_editor", "ffmpeg", "subtitle", "lm_studio", "copy", "dubbing",
    "clip_short", "cover", "publish", "batch", "web", "logging", "output", "pipeline",
    "video_quality", "notifications", "rate_limit", "rag", "video_qc", "scheduler",
    "distributed", "offline", "gpu_budget", "publish_preflight", "browser_publish",
    "platform_extra", "i18n_workflow", "team", "tenant",
    "cloud_storage", "webhook_trigger", "audio_enhance", "scene_detect",
}


def validate_config(cfg: dict[str, Any]) -> list[str]:
    """返回配置警告/错误列表，空列表表示通过。"""
    issues: list[str] = []
    for sec in REQUIRED_SECTIONS:
        if sec not in cfg:
            issues.append(f"缺少推荐配置节: {sec}")
    wcfg = cfg.get("whisper") or {}
    if wcfg.get("device") not in (None, "cuda", "cpu"):
        issues.append("whisper.device 应为 cuda 或 cpu")
    vq = cfg.get("video_quality") or {}
    enc = vq.get("encoder", "libx264")
    if enc not in ("libx264", "h264_nvenc", "copy"):
        issues.append(f"video_quality.encoder 未知: {enc}")
    web = cfg.get("web") or {}
    port = web.get("port", 8766)
    if not isinstance(port, int) or port < 1 or port > 65535:
        issues.append("web.port 无效")
    unknown = set(cfg.keys()) - KNOWN_SECTIONS - {"workflow", "terminology", "diarization", "broll", "vision", "i18n", "hot_topics", "intro_outro", "sensitive_scan", "whisperx", "capcut", "bgm_beat", "account_matrix", "job_backup", "presets"}
    for k in sorted(unknown):
        issues.append(f"未识别的配置节: {k}（可能是拼写错误）")
    return issues
