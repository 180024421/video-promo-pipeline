from __future__ import annotations

import json
import smtplib
import urllib.request
from email.mime.text import MIMEText
from typing import Any

from rich.console import Console

console = Console()


def notify_job_event(event: str, job_name: str, payload: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    ncfg = cfg.get("notifications") or {}
    if not ncfg.get("enabled", False):
        return {"skipped": True}

    results: dict[str, Any] = {}
    msg = _format_message(event, job_name, payload)

    wh = ncfg.get("webhook_url", "")
    if wh:
        results["webhook"] = _post_json(wh, {"event": event, "job": job_name, "message": msg, **payload})

    ww = ncfg.get("wechat_work_webhook", "")
    if ww:
        results["wechat_work"] = _post_json(ww, {"msgtype": "text", "text": {"content": msg}})

    email_cfg = ncfg.get("email") or {}
    if email_cfg.get("enabled") and email_cfg.get("to"):
        results["email"] = _send_email(email_cfg, f"[video-promo] {event}: {job_name}", msg)

    dt = ncfg.get("dingtalk_webhook", "")
    if dt:
        results["dingtalk"] = _post_json(dt, {"msgtype": "text", "text": {"content": msg}})

    tg = ncfg.get("telegram") or {}
    if tg.get("bot_token") and tg.get("chat_id"):
        url = f"https://api.telegram.org/bot{tg['bot_token']}/sendMessage"
        results["telegram"] = _post_json(url, {"chat_id": tg["chat_id"], "text": msg})

    if results:
        console.print(f"[green]通知已发送[/green] {event} {job_name}")
    return results


def _format_message(event: str, job_name: str, payload: dict[str, Any]) -> str:
    err = payload.get("error", "")
    step = payload.get("step", "")
    total = payload.get("total_seconds", "")
    lines = [f"任务: {job_name}", f"事件: {event}"]
    if step:
        lines.append(f"步骤: {step}")
    if err:
        lines.append(f"错误: {err}")
    if total:
        lines.append(f"总耗时: {total}s")
    return "\n".join(lines)


def _post_json(url: str, data: dict[str, Any]) -> dict[str, Any]:
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"ok": True, "status": resp.status}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _send_email(ecfg: dict[str, Any], subject: str, body: str) -> dict[str, Any]:
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = ecfg.get("from", ecfg.get("user", ""))
        msg["To"] = ecfg["to"]
        with smtplib.SMTP(ecfg.get("host", "smtp.qq.com"), int(ecfg.get("port", 465))) as s:
            if ecfg.get("use_tls", True):
                s.starttls()
            if ecfg.get("user"):
                s.login(ecfg["user"], ecfg.get("password", ""))
            s.send_message(msg)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
