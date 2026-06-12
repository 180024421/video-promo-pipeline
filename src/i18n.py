from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from rich.console import Console

from .lm_client import call_lm, make_lm_client, parse_json_content
from .transcribe import segments_to_srt

console = Console()

_LANG_NAMES = {"en": "English", "ja": "Japanese", "ko": "Korean", "zh": "Chinese"}


def translate_narration(narration: dict[str, Any], cfg: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    icfg = cfg.get("i18n") or {}
    if not icfg.get("enabled", False):
        return narration

    target = icfg.get("target_language", "en")
    lang_name = _LANG_NAMES.get(target, target)
    segments = narration.get("segments") or []
    text_block = "\n".join(f'{i+1}. {s.get("text","")}' for i, s in enumerate(segments))

    prompt = textwrap.dedent(f"""\
        将以下配音文本逐条翻译为{lang_name}，保持编号与时间轴信息不变。
        输出 JSON：{{"segments":[{{"index":1,"text":"..."}}]}}
        不要 markdown。

        {text_block}
    """)
    client = make_lm_client(cfg)
    content = call_lm(client, prompt, cfg, f"你是专业翻译，输出{lang_name}。")
    data = parse_json_content(content)
    trans_segs = data.get("segments", []) if isinstance(data, dict) else []
    idx_map = {int(t.get("index", i + 1)): t.get("text", "") for i, t in enumerate(trans_segs)}

    new_segments: list[dict[str, Any]] = []
    for i, seg in enumerate(segments):
        new_segments.append({
            **seg,
            "text": idx_map.get(i + 1, seg.get("text", "")),
        })

    result = {**narration, "segments": new_segments, "language": target}
    out_path = out_dir / f"narration_{target}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"narration_{target}.srt").write_text(segments_to_srt(new_segments), encoding="utf-8")
    console.print(f"[green]多语言翻译[/green] {target} → {out_path}")
    return result
