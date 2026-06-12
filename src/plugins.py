from __future__ import annotations

import importlib
from typing import Any, Callable

from rich.console import Console

console = Console()

PluginFn = Callable[[dict[str, Any], dict[str, Any]], None]

HOOKS = ("after_transcribe", "before_copy", "after_pack", "before_dub")


def _load_plugin(spec: str) -> PluginFn | None:
    """spec: module.path:function_name"""
    if ":" in spec:
        mod_name, fn_name = spec.rsplit(":", 1)
    elif "." in spec:
        parts = spec.rsplit(".", 1)
        mod_name, fn_name = parts[0], parts[1]
    else:
        return None
    try:
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
        if callable(fn):
            return fn
    except Exception as e:
        console.print(f"[yellow]插件加载失败 {spec}: {e}[/yellow]")
    return None


def run_plugins(hook: str, ctx: dict[str, Any], cfg: dict[str, Any]) -> None:
    pcfg = cfg.get("pipeline") or {}
    plugins = pcfg.get("plugins") or {}
    specs = plugins.get(hook) or []
    if isinstance(specs, str):
        specs = [specs]
    for spec in specs:
        fn = _load_plugin(spec)
        if fn:
            console.print(f"[cyan]插件[/cyan] {hook} ← {spec}")
            fn(ctx, cfg)
