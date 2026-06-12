from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from rich.console import Console

from .config_loader import ROOT

console = Console()
USER_PLUGINS_DIR = ROOT / "plugins"


def discover_user_plugins() -> list[dict[str, str]]:
    USER_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, str]] = []
    for p in sorted(USER_PLUGINS_DIR.glob("*.py")):
        if p.name.startswith("_"):
            continue
        items.append({"name": p.stem, "path": str(p)})
    return items


def load_user_plugin_hook(hook: str, cfg: dict[str, Any]) -> Any:
    pcfg = cfg.get("pipeline") or {}
    user_plugins = pcfg.get("user_plugins") or []
    for name in user_plugins:
        path = USER_PLUGINS_DIR / f"{name}.py"
        if not path.exists():
            continue
        fn = _load_hook_from_file(path, hook)
        if fn:
            return fn
    return None


def run_user_plugins(hook: str, ctx: dict[str, Any], cfg: dict[str, Any]) -> None:
    for item in discover_user_plugins():
        path = Path(item["path"])
        fn = _load_hook_from_file(path, hook)
        if fn:
            console.print(f"[cyan]用户插件[/cyan] {path.stem}:{hook}")
            fn(ctx, cfg)


def _load_hook_from_file(path: Path, hook: str) -> Any:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return getattr(mod, hook, None)
    except Exception as e:
        console.print(f"[yellow]用户插件 {path.name}: {e}[/yellow]")
        return None
