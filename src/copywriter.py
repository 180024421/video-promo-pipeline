from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openai import OpenAI
from rich.console import Console

from .config_loader import ROOT

console = Console()

DEFAULT_PROMPT = """你是短视频技术推广文案助手。
人设：{persona}
主题：{topic}
章节摘要：
{chapter_outline}
转写全文：
---
{transcript}
---
请输出 JSON（不要 markdown 代码块），包含 bilibili 与 xiaohongshu 字段及 short_hook。"""


def load_prompt_template(cfg: dict[str, Any]) -> str:
    ccfg = cfg.get("copy") or {}
    rel = ccfg.get("prompt_file") or ""
    if rel:
        path = ROOT / rel
        if path.exists():
            return path.read_text(encoding="utf-8")
    return DEFAULT_PROMPT


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


def _call_lm(client: OpenAI, prompt: str, cfg: dict[str, Any]) -> str:
    lcfg = cfg.get("lm_studio", {})
    model = lcfg.get("model") or None
    kwargs: dict[str, Any] = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": lcfg.get("temperature", 0.7),
    }
    if model:
        kwargs["model"] = model
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def generate_copy(
    transcript: str,
    cfg: dict[str, Any],
    out_dir: Path,
    *,
    chapter_outline: str = "",
) -> dict[str, Any] | None:
    lcfg = cfg.get("lm_studio", {})
    if not lcfg.get("enabled", True):
        console.print("[yellow]已跳过 LM Studio 文案生成[/yellow]")
        return None

    ccfg = cfg.get("copy") or {}
    platforms = [p.lower() for p in (ccfg.get("platforms") or ["bilibili", "xiaohongshu"])]
    persona = ccfg.get("persona", "技术博主")
    topic = ccfg.get("topic", "")
    template = load_prompt_template(cfg)
    prompt = template.format(
        persona=persona,
        topic=topic or "（未指定）",
        chapter_outline=chapter_outline or "（无）",
        transcript=transcript[:12000],
    )
    if "platforms" not in template.lower():
        prompt += f"\n\n仅生成这些平台字段: {', '.join(platforms)}"

    client = OpenAI(
        base_url=lcfg.get("base_url", "http://127.0.0.1:1234/v1"),
        api_key=lcfg.get("api_key", "lm-studio"),
    )

    console.print("[cyan]LM Studio 生成推广文案[/cyan]")
    try:
        content = _call_lm(client, prompt, cfg)
        try:
            data = _parse_json_content(content)
        except json.JSONDecodeError:
            if lcfg.get("json_retry", True):
                retry_prompt = prompt + "\n\n上次输出不是合法 JSON，请只输出一个 JSON 对象，不要任何解释。"
                content = _call_lm(client, retry_prompt, cfg)
                data = _parse_json_content(content)
            else:
                data = {"raw": content}
    except Exception as e:
        console.print(f"[red]LM Studio 调用失败: {e}[/red]")
        return None

    # filter platforms
    if isinstance(data, dict):
        if "bilibili" not in platforms:
            data.pop("bilibili", None)
        if "xiaohongshu" not in platforms:
            data.pop("xiaohongshu", None)

    out_path = out_dir / "promo_copy.json"
    md_path = out_dir / "promo_copy.md"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = ["# 推广文案\n"]
    if isinstance(data, dict) and "bilibili" in data:
        b = data["bilibili"]
        md_lines.append("## B站\n\n### 标题候选\n")
        for t in b.get("titles", []):
            md_lines.append(f"- {t}\n")
        desc = b.get("description", "")
        md_lines.append(f"\n### 简介\n\n{desc}\n")
        md_lines.append(f"\n### 标签\n\n{', '.join(b.get('tags', []))}\n")
        if b.get("chapters"):
            md_lines.append("\n### 章节\n\n")
            for ch in b["chapters"]:
                md_lines.append(f"- {ch.get('time', '')} {ch.get('title', '')}\n")
        (out_dir / "bilibili_description.txt").write_text(desc, encoding="utf-8")
    if isinstance(data, dict) and "xiaohongshu" in data:
        x = data["xiaohongshu"]
        md_lines.append("\n## 小红书\n")
        md_lines.append(f"\n### 标题\n\n{x.get('title', '')}\n")
        md_lines.append(f"\n### 正文\n\n{x.get('body', '')}\n")
        md_lines.append(f"\n### 话题\n\n{' '.join(x.get('topics', []))}\n")
        body = f"{x.get('title', '')}\n\n{x.get('body', '')}\n\n{' '.join(x.get('topics', []))}"
        (out_dir / "xiaohongshu_post.txt").write_text(body, encoding="utf-8")
    if isinstance(data, dict) and data.get("short_hook"):
        md_lines.append(f"\n## 前三秒钩子\n\n{data['short_hook']}\n")
    if isinstance(data, dict) and data.get("raw"):
        md_lines.append(f"\n## 原始输出\n\n{data['raw']}\n")

    md_path.write_text("".join(md_lines), encoding="utf-8")
    console.print(f"[green]文案已生成[/green] {md_path}")
    return data
