from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from rich.console import Console

from .lm_client import call_lm, make_lm_client, parse_json_content

console = Console()


def _fallback_segments(segments: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    """无 LM 时直接使用转写分段作为配音稿。"""
    out: list[dict[str, Any]] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if len(text) <= max_chars:
            out.append({"start": seg["start"], "end": seg["end"], "text": text})
            continue
        # 过长句段按字数比例切分时间轴
        chunks = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
        span = max(seg["end"] - seg["start"], 0.5)
        step = span / len(chunks)
        for i, chunk in enumerate(chunks):
            start = seg["start"] + i * step
            end = start + step
            out.append({"start": start, "end": end, "text": chunk})
    return out


def _build_narration_prompt(
    transcript: str,
    segments: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> str:
    ncfg = cfg.get("narration") or {}
    mode = ncfg.get("mode", "commentary")
    style = ncfg.get("style", "专业解说，口语化，节奏紧凑")
    persona = ncfg.get("persona", "科技区 UP 主")
    max_chars = int(ncfg.get("max_segment_chars", 80))
    target_duration = ncfg.get("target_duration_sec")

    seg_preview = "\n".join(
        f'{s["start"]:.1f}-{s["end"]:.1f}s: {s.get("text", "")[:60]}'
        for s in segments[:80]
    )
    duration_hint = ""
    if target_duration:
        duration_hint = f"\n目标成片时长约 {target_duration} 秒，请精简解说，删除废话与重复。"

    mode_hint = {
        "commentary": "将原声内容改写成第三人称解说稿，保留关键信息，不要照读原文。",
        "read_aloud": "润色原文使其更适合口播，保持原意，轻微删改口癖。",
        "summarize": "高度浓缩为短视频解说，只保留核心卖点与步骤。",
    }.get(mode, "改写成适合配音的解说稿。")

    return textwrap.dedent(f"""\
        你是短视频配音编剧。人设：{persona}
        风格：{style}
        任务：{mode_hint}
        要求：
        - 输出 JSON，不要 markdown 代码块
        - segments 数组，每项含 start（秒）、end（秒）、text（配音文本）
        - 每段 text 不超过 {max_chars} 字，适合 TTS 朗读
        - start/end 必须落在原视频时间轴内，可合并相邻句段
        - 语言为中文，不要英文括号堆砌
        {duration_hint}

        原视频转写分段（时间轴参考）：
        ---
        {seg_preview}
        ---

        转写全文（前 8000 字）：
        ---
        {transcript[:8000]}
        ---

        JSON 格式：
        {{
          "title": "视频主题一句话",
          "segments": [
            {{"start": 0.0, "end": 5.2, "text": "开场解说..."}}
          ]
        }}
    """)


def generate_narration(
    transcript: str,
    segments: list[dict[str, Any]],
    cfg: dict[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    ncfg = cfg.get("narration") or {}
    if not ncfg.get("enabled", False):
        return {"enabled": False, "segments": segments, "title": ""}

    out_path = out_dir / "narration.json"
    max_chars = int(ncfg.get("max_segment_chars", 80))

    if not ncfg.get("use_lm", True):
        data = {
            "title": out_dir.name.split("_")[0],
            "segments": _fallback_segments(segments, max_chars),
            "source": "transcript",
        }
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]配音稿（原声润色）[/green] {len(data['segments'])} 段")
        return data

    lcfg = cfg.get("lm_studio") or {}
    if not lcfg.get("enabled", True):
        console.print("[yellow]LM Studio 未启用，使用原转写作为配音稿[/yellow]")
        data = {
            "title": out_dir.name.split("_")[0],
            "segments": _fallback_segments(segments, max_chars),
            "source": "transcript_fallback",
        }
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    client = make_lm_client(cfg)
    system = ncfg.get("system_prompt") or lcfg.get("system_prompt") or "你是专业的中文短视频配音编剧。"
    prompt = _build_narration_prompt(transcript, segments, cfg)

    console.print("[cyan]LM Studio 生成配音解说稿...[/cyan]")
    content = call_lm(client, prompt, cfg, system)
    data = parse_json_content(content)
    if not isinstance(data, dict) or "segments" not in data:
        raise ValueError("LM 返回的配音稿格式无效，缺少 segments")

    norm: list[dict[str, Any]] = []
    for seg in data["segments"]:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        norm.append({
            "start": float(seg.get("start", 0)),
            "end": float(seg.get("end", 0)),
            "text": text[:max_chars],
        })
    if not norm:
        norm = _fallback_segments(segments, max_chars)

    result = {
        "title": str(data.get("title", "")),
        "segments": norm,
        "source": "lm_studio",
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "narration_script.txt").write_text(
        "\n\n".join(s["text"] for s in norm),
        encoding="utf-8",
    )
    console.print(f"[green]配音解说稿已生成[/green] {out_path} ({len(norm)} 段)")
    return result
