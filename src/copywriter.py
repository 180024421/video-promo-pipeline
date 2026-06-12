from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Any

from openai import OpenAI, APITimeoutError
from rich.console import Console

from .config_loader import ROOT
from .chapters import build_chapters_from_segments
from .copy_enhance import post_process_copy

console = Console()


def _get_platform_cfg(cfg: dict[str, Any], platform: str) -> dict[str, Any]:
    """从新的平台嵌套配置或旧的顶层配置获取。"""
    copy_cfg = cfg.get("copy") or {}
    # 新格式：copy.bilibili.enabled
    if platform in copy_cfg and isinstance(copy_cfg[platform], dict):
        return copy_cfg[platform]
    # 旧格式兼容：copy.persona、copy.platforms 等
    return copy_cfg


def _platform_enabled(cfg: dict[str, Any], platform: str) -> bool:
    pc = _get_platform_cfg(cfg, platform)
    return pc.get("enabled", True)


def _load_prompt_override(cfg: dict[str, Any], platform: str) -> str | None:
    """如果用户写了 platform.prompt_override，直接用它。"""
    pc = _get_platform_cfg(cfg, platform)
    override = pc.get("prompt_override", "")
    if override:
        return override
    # 旧格式 prompt_file
    rel = (cfg.get("copy") or {}).get("prompt_file", "")
    if rel:
        path = ROOT / rel
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


def _build_system_prompt(cfg: dict[str, Any], platform: str) -> str | None:
    """构建系统提示词或返回 None。"""
    pc = _get_platform_cfg(cfg, platform)
    sp = pc.get("system_prompt", "")
    if sp:
        return sp
    global_sp = (cfg.get("lm_studio") or {}).get("system_prompt", "")
    return global_sp or None


def _build_platform_prompt(
    cfg: dict[str, Any],
    platform: str,
    transcript: str,
    chapter_outline: str,
) -> str:
    """为特定平台构建结构化 prompt。"""
    pc = _get_platform_cfg(cfg, platform)
    override = _load_prompt_override(cfg, platform)
    if override:
        # 允许用户在 override 里用模板变量
        return override.format(
            persona=pc.get("persona", "技术博主"),
            style=pc.get("style", ""),
            tone=pc.get("tone", ""),
            audience=pc.get("audience", ""),
            topic=pc.get("content_type", ""),
            keywords=", ".join(pc.get("keywords", [])),
            chapter_outline=chapter_outline or "（无）",
            transcript=transcript[:12000],
        )

    # 统一助手身份
    lines: list[str] = [
        f"你是一位专业的 {platform} 内容运营助手。",
        f"人设：{pc.get('persona', '技术博主')}",
        f"风格：{pc.get('style', '干货分享')}",
        f"语气：{pc.get('tone', '专业且接地气')}",
        f"受众：{pc.get('audience', '技术人员')}",
        f"内容定位：{pc.get('content_type', '技术分享')}",
    ]
    if pc.get("keywords"):
        lines.append(f"关键词：{', '.join(pc['keywords'])}")

    # 禁用词
    forbidden = set(
        (cfg.get("copy") or {}).get("general", {}).get("global_forbidden_words", [])
    )
    local_fb = pc.get("forbidden_words", [])
    forbidden.update(local_fb)
    if forbidden:
        lines.append(f"禁词（绝对不可用）：{', '.join(sorted(forbidden))}")

    lines.append("\n以下是视频转写内容：")
    lines.append(f"章节摘要：\n{chapter_outline or '（无）'}\n")
    lines.append(f"转写全文（前 12000 字）：\n---\n{transcript[:12000]}\n---\n")

    instructions: list[str] = []
    ctas: list[str] = []

    if platform == "bilibili":
        max_title = pc.get("max_title_length", 40)
        max_desc = pc.get("max_description_length", 500)
        max_tags = pc.get("max_tags", 10)
        instructions.extend([
            f"请为 B 站生成推广内容：",
            f"- titles: 标题候选数组，每个不超过 {max_title} 字，共 5 个",
            f"- description: 简介不超过 {max_desc} 字，不要放微信/QQ/外链",
            f"- tags: 标签数组，最多 {max_tags} 个",
        ])
        if pc.get("chapters_enabled"):
            instructions.append("- chapters: 章节时间轴数组 [{\"time\":\"mm:ss\",\"title\":\"...\"}]")
        if pc.get("call_to_action"):
            ctas.append(f"CTA：{pc['call_to_action']}")
        instructions.append("输出 JSON，不要有 markdown 代码块。")
        lines.append("\n" + "\n".join(instructions))
        if ctas:
            lines.append("\n".join(ctas))
        lines.append(
            '\nJSON 格式：\n'
            '{\n'
            '  "bilibili": {\n'
            '    "titles": ["...", "..."],\n'
            '    "description": "...",\n'
            '    "tags": ["..."],\n'
            '    "chapters": [{"time":"00:00","title":"开场"}]\n'
            '  },\n'
            '  "short_hook": "前三秒钩子"\n'
            '}'
        )

    elif platform == "xiaohongshu":
        max_title = pc.get("max_title_length", 20)
        max_body = pc.get("max_body_length", 1000)
        max_topics = pc.get("max_topics", 10)
        instructions.extend([
            f"请为小红书生成笔记内容：",
            f"- title: 标题，不超过 {max_title} 字，带数字或痛点",
            f"- body: 正文不超过 {max_body} 字，分段、口语化、像笔记",
            f"- topics: 话题标签数组，最多 {max_topics} 个，带 #",
        ])
        if pc.get("emoji_usage"):
            emojis = pc.get("emoji_set", ["💻", "🔥"])
            instructions.append(f"- 可适当使用 emoji：{', '.join(emojis)}")
        if pc.get("numbered_tips"):
            instructions.append("- 使用数字列表结构，如\"3 个技巧/5 步搞定\"")
        if pc.get("highlight_boxes"):
            instructions.append("- 关键信息用 emoji 或符号（📌 ✅ ⚡）强调")
        if pc.get("call_to_action"):
            ctas.append(f"CTA：{pc['call_to_action']}")
        instructions.append("输出 JSON，不要有 markdown 代码块。")
        lines.append("\n" + "\n".join(instructions))
        if ctas:
            lines.append("\n".join(ctas))
        lines.append(
            '\nJSON 格式：\n'
            '{\n'
            '  "xiaohongshu": {\n'
            '    "title": "...",\n'
            '    "body": "...",\n'
            '    "topics": ["#话题1", "#话题2"]\n'
            '  },\n'
            '  "short_hook": "前三秒钩子"\n'
            '}'
        )

    elif platform == "douyin":
        max_title = pc.get("max_title_length", 25)
        max_body = pc.get("max_body_length", 300)
        instructions.extend([
            f"请为抖音生成文案：",
            f"- title: 标题不超过 {max_title} 字，节奏快抓人",
            f"- body: 正文不超过 {max_body} 字",
            f"- hashtags: 带 # 的话题标签",
        ])
        if pc.get("hook_first_3_seconds"):
            instructions.append("- short_hook 必须强调前 3 秒钩子")
        instructions.append("输出 JSON，不要有 markdown 代码块。")
        lines.append("\n" + "\n".join(instructions))
        lines.append(
            '\nJSON 格式：\n'
            '{\n'
            '  "douyin": {\n'
            '    "title": "...",\n'
            '    "body": "...",\n'
            '    "hashtags": ["#..."]\n'
            '  },\n'
            '  "short_hook": "前三秒钩子"\n'
            '}'
        )

    elif platform == "wechat_mp":
        max_title = pc.get("max_title_length", 30)
        max_body = pc.get("max_body_length", 3000)
        instructions.extend([
            f"请为微信公众号生成文章推广文案：",
            f"- title: 标题不超过 {max_title} 字",
            f"- summary: 文章摘要 100 字以内",
            f"- body: 正文不超过 {max_body} 字，可使用 Markdown",
        ])
        if pc.get("include_toc"):
            instructions.append("- 包含内容目录大纲")
        if pc.get("call_to_action"):
            instructions.append(f"- CTA：{pc['call_to_action']}")
        instructions.append("输出 JSON，不要有 markdown 代码块。")
        lines.append("\n" + "\n".join(instructions))
        lines.append(
            '\nJSON 格式：\n'
            '{\n'
            '  "wechat_mp": {\n'
            '    "title": "...",\n'
            '    "summary": "...",\n'
            '    "body": "..."\n'
            '  }\n'
            '}'
        )

    return "\n".join(lines)


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


def _call_lm(
    client: OpenAI,
    prompt: str,
    cfg: dict[str, Any],
    system_prompt: str | None = None,
) -> str:
    lcfg = cfg.get("lm_studio", {})
    model = lcfg.get("model") or None

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {
        "messages": messages,
        "temperature": lcfg.get("temperature", 0.7),
        "max_tokens": lcfg.get("max_tokens", 4096),
        "timeout": lcfg.get("timeout", 120),
    }
    if model:
        kwargs["model"] = model
    for key in ("top_p", "frequency_penalty", "presence_penalty", "seed"):
        val = lcfg.get(key)
        if val is not None:
            kwargs[key] = val

    last_err: Exception | None = None
    max_retries = int(lcfg.get("max_retries", 3))
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(**kwargs)
            from .lm_usage import record_from_response
            record_from_response(resp, label=platform)
            return resp.choices[0].message.content or ""
        except APITimeoutError as e:
            last_err = e
            console.print(f"[yellow]LM Studio 请求超时（第 {attempt} 次），稍后重试...[/yellow]")
        except Exception as e:
            last_err = e
            console.print(f"[yellow]LM Studio 请求失败（第 {attempt} 次）：{e}[/yellow]")
    raise last_err or RuntimeError("LM Studio 请求全部失败")


def _build_hooks(
    client: OpenAI,
    transcript: str,
    cfg: dict[str, Any],
    system_prompt: str | None = None,
) -> list[str]:
    gcfg = (cfg.get("copy") or {}).get("general", {})
    if not gcfg.get("short_hook_enabled", True):
        return []
    style = gcfg.get("short_hook_style", "痛点反问式")
    count = int(gcfg.get("short_hook_count", 3))
    prompt = textwrap.dedent(f"""\
        你是短视频钩子文案专家。
        请根据以下视频转写内容，生成 {count} 个前三秒开场钩子。
        风格：{style}
        要求：
        - 每个钩子一句话，不超过 25 字
        - 必须让用户想继续往下看
        - 不要用问句堆砌，要有冲击力

        转写内容前 2000 字：
        ---
        {transcript[:2000]}
        ---

        输出 JSON 数组格式：["钩子1", "钩子2", "钩子3"]
    """)
    try:
        content = _call_lm(client, prompt, cfg, system_prompt)
        data = _parse_json_content(content)
        if isinstance(data, list):
            return [str(h) for h in data]
        elif isinstance(data, dict) and "hooks" in data:
            return [str(h) for h in data["hooks"]]
    except Exception as e:
        console.print(f"[yellow]钩子生成失败: {e}[/yellow]")
    return []


def _filter_forbidden(data: dict[str, Any], cfg: dict[str, Any], platform: str) -> dict[str, Any]:
    """递归扫描 dict/list/str，替换禁用词。"""
    forbidden = set(
        (cfg.get("copy") or {}).get("general", {}).get("global_forbidden_words", [])
    )
    pc = _get_platform_cfg(cfg, platform)
    forbidden.update(pc.get("forbidden_words", []))
    if not forbidden:
        return data
    pattern = re.compile("|".join(re.escape(w) for w in forbidden), flags=re.IGNORECASE)

    def _clean(obj: Any) -> Any:
        if isinstance(obj, str):
            return pattern.sub(lambda m: "█" * len(m.group()), obj)
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        return obj

    return _clean(data)


def generate_copy(
    transcript: str,
    cfg: dict[str, Any],
    out_dir: Path,
    *,
    chapter_outline: str = "",
    segments: list[dict[str, Any]] | None = None,
    only_platforms: list[str] | None = None,
) -> dict[str, Any] | None:
    lcfg = cfg.get("lm_studio", {})
    if not lcfg.get("enabled", True):
        console.print("[yellow]已跳过 LM Studio 文案生成[/yellow]")
        return None

    client = OpenAI(
        base_url=lcfg.get("base_url", "http://127.0.0.1:1234/v1"),
        api_key=lcfg.get("api_key", "lm-studio"),
    )

    platforms = ["bilibili", "xiaohongshu", "douyin", "wechat_mp"]
    enabled = [p for p in platforms if _platform_enabled(cfg, p)]
    if only_platforms:
        enabled = [p for p in enabled if p in only_platforms]
    if not enabled:
        console.print("[yellow]没有启用的文案平台[/yellow]")
        return None

    # 生成统一钩子（提升效率：只需调一次）
    system_prompt = _build_system_prompt(cfg, "bilibili")  # 统一身份可用
    # 实际上每个平台可能 system prompt 不同，这里先通用
    system_prompt = (cfg.get("lm_studio") or {}).get("system_prompt", "") or system_prompt

    hooks = _build_hooks(client, transcript, cfg, system_prompt)

    all_data: dict[str, Any] = {}
    for platform in enabled:
        console.print(f"[cyan]生成 {platform} 文案...[/cyan]")
        prompt = _build_platform_prompt(cfg, platform, transcript, chapter_outline)
        try:
            content = _call_lm(client, prompt, cfg, system_prompt)
            data = _parse_json_content(content)
            if isinstance(data, dict):
                data = _filter_forbidden(data, cfg, platform)
                all_data.update(data)
            else:
                all_data[f"{platform}_raw"] = content
        except Exception as e:
            console.print(f"[red]{platform} 文案生成失败: {e}[/red]")

    if hooks:
        all_data["short_hooks"] = hooks

    all_data = post_process_copy(all_data, cfg, transcript)

    if _platform_enabled(cfg, "bilibili"):
        ch = build_chapters_from_segments(segments or [], cfg) if segments else []
        if ch and isinstance(all_data.get("bilibili"), dict):
            all_data["bilibili"]["chapters"] = ch
            lines = [f"{c['time']} {c['title']}" for c in ch]
            (out_dir / "bilibili_chapters.txt").write_text("\n".join(lines), encoding="utf-8")

    # 写入各平台单独文件
    _write_outputs(all_data, out_dir, cfg)

    return all_data


def _write_outputs(data: dict[str, Any], out_dir: Path, cfg: dict[str, Any]) -> None:
    gen = (cfg.get("copy") or {}).get("general", {})
    formats = gen.get("export_formats", ["json", "markdown"])

    if "json" in formats:
        (out_dir / "promo_copy.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    md_lines: list[str] = ["# 推广文案\n"]

    if "bilibili" in data and isinstance(data["bilibili"], dict):
        b = data["bilibili"]
        md_lines.append("## B站\n\n")
        if b.get("titles"):
            md_lines.append("### 标题候选\n")
            for t in b["titles"]:
                md_lines.append(f"- {t}\n")
        desc = b.get("description", "")
        md_lines.append(f"\n### 简介\n\n{desc}\n")
        if b.get("tags"):
            md_lines.append(f"\n### 标签\n\n{', '.join(b['tags'])}\n")
        if b.get("chapters"):
            md_lines.append("\n### 章节\n\n")
            for ch in b["chapters"]:
                md_lines.append(f"- {ch.get('time', '')} {ch.get('title', '')}\n")
        (out_dir / "bilibili_description.txt").write_text(desc, encoding="utf-8")

    if "xiaohongshu" in data and isinstance(data["xiaohongshu"], dict):
        x = data["xiaohongshu"]
        md_lines.append("\n## 小红书\n\n")
        md_lines.append(f"### 标题\n\n{x.get('title', '')}\n")
        md_lines.append(f"\n### 正文\n\n{x.get('body', '')}\n")
        if x.get("topics"):
            md_lines.append(f"\n### 话题\n\n{' '.join(x['topics'])}\n")
        body = f"{x.get('title', '')}\n\n{x.get('body', '')}\n\n{' '.join(x.get('topics', []))}"
        (out_dir / "xiaohongshu_post.txt").write_text(body, encoding="utf-8")

    if "douyin" in data and isinstance(data["douyin"], dict):
        d = data["douyin"]
        md_lines.append("\n## 抖音\n\n")
        md_lines.append(f"### 标题\n\n{d.get('title', '')}\n")
        md_lines.append(f"\n### 正文\n\n{d.get('body', '')}\n")
        if d.get("hashtags"):
            md_lines.append(f"\n### 话题\n\n{' '.join(d['hashtags'])}\n")

    if "wechat_mp" in data and isinstance(data["wechat_mp"], dict):
        w = data["wechat_mp"]
        md_lines.append("\n## 微信公众号\n\n")
        md_lines.append(f"### 标题\n\n{w.get('title', '')}\n")
        md_lines.append(f"\n### 摘要\n\n{w.get('summary', '')}\n")
        md_lines.append(f"\n### 正文\n\n{w.get('body', '')}\n")

    if data.get("short_hooks"):
        md_lines.append("\n## 前三秒钩子候选\n\n")
        for i, h in enumerate(data["short_hooks"], 1):
            md_lines.append(f"{i}. {h}\n")
    elif data.get("short_hook"):
        md_lines.append(f"\n## 前三秒钩子\n\n{data['short_hook']}\n")

    if data.get("raw"):
        md_lines.append(f"\n## 原始输出\n\n{data['raw']}\n")

    if "markdown" in formats:
        (out_dir / "promo_copy.md").write_text("".join(md_lines), encoding="utf-8")
        console.print(f"[green]文案已生成[/green] {out_dir / 'promo_copy.md'}")
