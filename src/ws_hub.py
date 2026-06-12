from __future__ import annotations

import asyncio
import json
from typing import Any

_connections: set[Any] = set()
_lock = asyncio.Lock()


async def register(ws: Any) -> None:
    async with _lock:
        _connections.add(ws)


async def unregister(ws: Any) -> None:
    async with _lock:
        _connections.discard(ws)


async def broadcast(payload: dict[str, Any]) -> None:
    dead: list[Any] = []
    msg = json.dumps(payload, ensure_ascii=False)
    async with _lock:
        conns = list(_connections)
    for ws in conns:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        await unregister(ws)


def broadcast_sync(payload: dict[str, Any]) -> None:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(broadcast(payload))
        else:
            loop.run_until_complete(broadcast(payload))
    except RuntimeError:
        asyncio.run(broadcast(payload))
