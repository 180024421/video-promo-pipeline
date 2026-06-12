from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI
from rich.console import Console

console = Console()

PROMPT_TEMPLATE = """你是短视频技术推广文案助手。

人设：{persona}

以下是视频自动转写全文（可能有少量识别错误，请自行修正技术术语如 ADB、YOLO、Spring Boot）：

---
{transcript}
---

请输出 JSON（不要 markdown 代码块），结构如下：
{{
  "bilibili": {{
    "titles": ["标题1", "标题2", "标题3", "标题4", "标题5"],
    "description": "200字以内简介，不含微信/QQ/外链",
    "tags": ["标签1", "标签2"],
    "chapters": [{{"time": "00:00", "title": "章节名"}}]
  }},
  "xiaohongshu": {{
    "title": "小红书标题",
    "body": "300字以内正文，口语化，无联系方式",
    "topics": ["#话题1", "#话题2"]
  }},
  "short_hook": "前3秒口播钩子，一句话"
}}

要求：专业、干货、不夸大、不说副业暴富、不提外挂搬砖。"""


def generate_copy(transcript: str, cfg: dict[str, Any], out_dir: Path) -> dict[str, Any] | None:
    lcfg = cfg.get("lm_studio", {})
    if not lcfg.get("enabled", True):
        console.print("[yellow]已跳过 LM Studio 文案生成[/yellow]")
        return None

    persona = cfg.get("copy", {}).get("persona", "技术博主")
    prompt = PROMPT_TEMPLATE.format(persona=persona, transcript=transcript[:12000])

    client = OpenAI(
        base_url=lcfg.get("base_url", "http://127.0.0.1:1234/v1"),
        api_key=lcfg.get("api_key", "lm-studio"),
    )

    model = lcfg.get("model") or None
    kwargs: dict[str, Any] = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": lcfg.get("temperature", 0.7),
    }
    if model:
        kwargs["model"] = model

    console.print("[cyan]LM Studio 生成推广文案[/cyan]")
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:
        console.print(f"[red]LM Studio 调用失败: {e}[/red]")
        console.print("[yellow]请确认 LM Studio 已启动并开启 Local Server (默认 1234)[/yellow]")
        return None

    content = resp.choices[0].message.content or ""
    # 尝试解析 JSON
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"raw": content}

    out_path = out_dir / "promo_copy.json"
    md_path = out_dir / "promo_copy.md"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = ["# 推广文案\n"]
    if isinstance(data, dict) and "bilibili" in data:
        b = data["bilibili"]
        md_lines.append("## B站\n")
        md_lines.append("### 标题候选\n")
        for t in b.get("titles", []):
            md_lines.append(f"- {t}\n")
        md_lines.append(f"\n### 简介\n\n{b.get('description', '')}\n")
        md_lines.append(f"\n### 标签\n\n{', '.join(b.get('tags', []))}\n")
    if isinstance(data, dict) and "xiaohongshu" in data:
        x = data["xiaohongshu"]
        md_lines.append("\n## 小红书\n")
        md_lines.append(f"\n### 标题\n\n{x.get('title', '')}\n")
        md_lines.append(f"\n### 正文\n\n{x.get('body', '')}\n")
        md_lines.append(f"\n### 话题\n\n{' '.join(x.get('topics', []))}\n")
    if isinstance(data, dict) and data.get("short_hook"):
        md_lines.append(f"\n## 前三秒钩子\n\n{data['short_hook']}\n")
    if data.get("raw"):
        md_lines.append(f"\n## 原始输出\n\n{data['raw']}\n")

    md_path.write_text("".join(md_lines), encoding="utf-8")
    console.print(f"[green]文案已生成[/green] {md_path}")
    return data
