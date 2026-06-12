from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

_buckets: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(client_id: str, *, max_per_minute: int = 60) -> tuple[bool, str]:
    now = time.time()
    window = _buckets[client_id]
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= max_per_minute:
        return False, "请求过于频繁，请稍后再试"
    window.append(now)
    return True, ""
