from __future__ import annotations

import asyncio
import base64
import json
import urllib.request
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


async def _edge_tts(text: str, voice: str, rate: str, volume: str, out_path: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice, rate=rate, volume=volume).save(str(out_path))


def _azure_tts(text: str, cfg: dict[str, Any], out_path: Path) -> None:
    acfg = (cfg.get("dubbing") or {}).get("azure") or {}
    key = acfg.get("key", "")
    region = acfg.get("region", "eastasia")
    voice = acfg.get("voice") or (cfg.get("dubbing") or {}).get("voice", "zh-CN-YunxiNeural")
    if not key:
        raise RuntimeError("Azure TTS 需要配置 dubbing.azure.key")

    import urllib.parse

    ssml = (
        f'<speak version="1.0" xml:lang="zh-CN">'
        f'<voice name="{voice}">{text}</voice></speak>'
    )
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    req = urllib.request.Request(
        url,
        data=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out_path.write_bytes(resp.read())


def _gpt_sovits_tts(text: str, cfg: dict[str, Any], out_path: Path) -> None:
    gcfg = (cfg.get("dubbing") or {}).get("gpt_sovits") or {}
    base = gcfg.get("base_url", "http://127.0.0.1:9880").rstrip("/")
    ref = gcfg.get("reference_audio") or (cfg.get("dubbing") or {}).get("voice_clone", {}).get("reference_audio", "")
    payload: dict[str, Any] = {
        "text": text,
        "text_language": gcfg.get("text_language", "zh"),
    }
    if ref and Path(ref).exists():
        payload["refer_wav_path"] = ref
        payload["prompt_text"] = gcfg.get("prompt_text", "")
        payload["prompt_language"] = gcfg.get("prompt_language", "zh")

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out_path.write_bytes(resp.read())
    except Exception:
        # 兼容另一种 API 路径
        req2 = urllib.request.Request(
            f"{base}/tts",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=120) as resp:
            body = resp.read()
            try:
                j = json.loads(body)
                if "audio" in j:
                    out_path.write_bytes(base64.b64decode(j["audio"]))
                    return
            except json.JSONDecodeError:
                pass
            out_path.write_bytes(body)


def synthesize_one(text: str, out_path: Path, cfg: dict[str, Any]) -> None:
    dcfg = cfg.get("dubbing") or {}
    engine = dcfg.get("engine", "edge-tts")
    voice = dcfg.get("voice", "zh-CN-YunxiNeural")
    rate = dcfg.get("rate", "+0%")
    volume = dcfg.get("volume", "+0%")

    if engine == "azure":
        _azure_tts(text, cfg, out_path)
    elif engine == "gpt-sovits":
        _gpt_sovits_tts(text, cfg, out_path)
    else:
        asyncio.run(_edge_tts(text, voice, rate, volume, out_path))


def synthesize_all_segments(segments: list[dict[str, Any]], cfg: dict[str, Any], out_dir: Path) -> Path:
    dcfg = cfg.get("dubbing") or {}
    engine = dcfg.get("engine", "edge-tts")
    tts_dir = out_dir / "tts_segments"
    tts_dir.mkdir(exist_ok=True)

    async def _edge_batch() -> None:
        tasks = []
        for i, seg in enumerate(segments):
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            out_path = tts_dir / f"seg_{i:04d}.mp3"
            voice = dcfg.get("voice", "zh-CN-YunxiNeural")
            tasks.append(_edge_tts(text, voice, dcfg.get("rate", "+0%"), dcfg.get("volume", "+0%"), out_path))
        if tasks:
            await asyncio.gather(*tasks)

    console.print(f"[cyan]TTS 合成[/cyan] engine={engine} segments={len(segments)}")
    if engine == "edge-tts":
        asyncio.run(_edge_batch())
    else:
        for i, seg in enumerate(segments):
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            synthesize_one(text, tts_dir / f"seg_{i:04d}.mp3", cfg)
    return tts_dir
