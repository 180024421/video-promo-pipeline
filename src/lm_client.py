from __future__ import annotations

import json
import re
import time
from typing import Any

from openai import APITimeoutError, OpenAI
from rich.console import Console

from .lm_usage import record_from_response

console = Console()


def make_lm_client(cfg: dict[str, Any]) -> OpenAI:
    lcfg = cfg.get("lm_studio") or {}
    return OpenAI(
        base_url=lcfg.get("base_url", "http://127.0.0.1:1234/v1"),
        api_key=lcfg.get("api_key", "lm-studio"),
    )


def parse_json_content(content: str) -> Any:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


def call_lm(
    client: OpenAI,
    prompt: str,
    cfg: dict[str, Any],
    system_prompt: str | None = None,
) -> str:
    lcfg = cfg.get("lm_studio") or {}
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
            t0 = time.perf_counter()
            resp = client.chat.completions.create(**kwargs)
            record_from_response(resp, label=kwargs.get("model") or "lm", duration_ms=int((time.perf_counter() - t0) * 1000))
            return resp.choices[0].message.content or ""
        except APITimeoutError as e:
            last_err = e
            console.print(f"[yellow]LM Studio 请求超时（第 {attempt} 次），稍后重试...[/yellow]")
        except Exception as e:
            last_err = e
            console.print(f"[yellow]LM Studio 请求失败（第 {attempt} 次）：{e}[/yellow]")
    raise last_err or RuntimeError("LM Studio 请求全部失败")
