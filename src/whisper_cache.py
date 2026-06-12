from __future__ import annotations

from typing import Any

_model_cache: dict[str, Any] = {}


def get_whisper_model(model_size: str, device: str, compute_type: str) -> Any:
    """进程内复用 Whisper 模型，避免重复加载。"""
    key = f"{model_size}|{device}|{compute_type}"
    if key in _model_cache:
        return _model_cache[key]
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    _model_cache[key] = model
    return model


def clear_whisper_cache() -> None:
    _model_cache.clear()
