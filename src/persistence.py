"""SQLite 持久化：任务状态、历史、聚合查询。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .config_loader import ROOT

DB_PATH = ROOT / "data" / "pipeline.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            name TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending',
            step TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT,
            summary TEXT
        );
        CREATE TABLE IF NOT EXISTS step_timing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            step_name TEXT NOT NULL,
            elapsed_sec REAL,
            recorded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS publish_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT,
            platform TEXT,
            url TEXT,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            recorded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS finetune_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            score REAL,
            detail TEXT,
            created_at TEXT
        );
    """)
    con.commit()
    con.close()


def upsert_job(name: str, **kw: Any) -> None:
    con = _conn()
    keys = ", ".join(kw.keys())
    vals = ", ".join("?" for _ in kw)
    con.execute(
        f"INSERT INTO jobs (name, {keys}) VALUES (?, {vals}) ON CONFLICT(name) DO UPDATE SET {', '.join(f'{k}=excluded.{k}' for k in kw)}",
        [name, *kw.values()],
    )
    con.commit()
    con.close()


def list_jobs(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    con = _conn()
    if status:
        rows = con.execute("SELECT * FROM jobs WHERE status=? ORDER BY updated_at DESC LIMIT ?", (status, limit))
    else:
        rows = con.execute("SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,))
    result = [dict(r) for r in rows.fetchall()]
    con.close()
    return result


def add_step_timing(job_name: str, step_name: str, elapsed_sec: float) -> None:
    from datetime import datetime, timezone

    con = _conn()
    con.execute(
        "INSERT INTO step_timing (job_name, step_name, elapsed_sec, recorded_at) VALUES (?, ?, ?, ?)",
        (job_name, step_name, elapsed_sec, datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


def step_timing_aggregate() -> list[dict[str, Any]]:
    con = _conn()
    rows = con.execute("SELECT step_name, AVG(elapsed_sec) as avg_sec, COUNT(*) as cnt FROM step_timing GROUP BY step_name ORDER BY avg_sec DESC")
    result = [dict(r) for r in rows.fetchall()]
    con.close()
    return result


def record_publish_data(job_name: str, platform: str, **stats: Any) -> None:
    from datetime import datetime, timezone

    con = _conn()
    con.execute(
        "INSERT INTO publish_data (job_name, platform, url, views, likes, comments, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (job_name, platform, stats.get("url", ""), stats.get("views", 0), stats.get("likes", 0), stats.get("comments", 0), datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


def publish_aggregate() -> list[dict[str, Any]]:
    con = _conn()
    rows = con.execute("SELECT platform, SUM(views) as total_views, SUM(likes) as total_likes, COUNT(*) as cnt FROM publish_data GROUP BY platform")
    result = [dict(r) for r in rows.fetchall()]
    con.close()
    return result


def record_feedback_db(category: str, score: float, detail: str = "") -> None:
    from datetime import datetime, timezone

    con = _conn()
    con.execute(
        "INSERT INTO finetune_feedback (category, score, detail, created_at) VALUES (?, ?, ?, ?)",
        (category, score, detail, datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


init_db()
