from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

console = Console()

BILI_OAUTH_URL = "https://open.bilibili.com/oauth2/access_token"
BILI_PREUPLOAD = "https://member.bilibili.com/preupload"
BILI_UPLOAD_INIT = "https://member.bilibili.com/arcopen/fn/archive/upload"
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB

ProgressCallback = Callable[[int, str], None] | None


def _sign_params(params: dict[str, Any], secret: str) -> str:
    sorted_keys = sorted(params.keys())
    raw = "".join(f"{k}{params[k]}" for k in sorted_keys) + secret
    return hashlib.md5(raw.encode()).hexdigest()


def _http_json(url: str, data: dict[str, Any] | None = None, headers: dict[str, str] | None = None, method: str = "GET") -> dict[str, Any]:
    hdrs = {"User-Agent": "video-promo-pipeline/3.4", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def _http_put_chunk(url: str, chunk: bytes, headers: dict[str, str]) -> None:
    req = urllib.request.Request(url, data=chunk, headers=headers, method="PUT")
    with urllib.request.urlopen(req, timeout=300) as resp:
        if resp.status not in (200, 201, 204):
            raise RuntimeError(f"分片上传失败 HTTP {resp.status}")


def _save_progress(job_dir: Path | None, payload: dict[str, Any]) -> None:
    if not job_dir:
        return
    path = job_dir / "bilibili_upload_progress.json"
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_access_token(client_id: str, client_secret: str, refresh_token: str = "") -> dict[str, Any]:
    if not refresh_token:
        raise RuntimeError("需要配置 publish.bilibili.refresh_token 或完成 OAuth 授权")
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    return _http_json(BILI_OAUTH_URL, data, method="POST")


def _init_preupload(access_token: str, filename: str, file_size: int) -> dict[str, Any]:
    """获取 B 站 preupload 信息（UPOS 分片上传）。"""
    params = {
        "name": filename,
        "size": str(file_size),
        "r": "upos",
        "profile": "ugcupos/bup",
        "ssl": "0",
        "version": "2.8.12",
        "access_token": access_token,
    }
    url = f"{BILI_PREUPLOAD}?{urllib.parse.urlencode(params)}"
    return _http_json(url)


def _upload_chunks_upos(
    video_path: Path,
    upos_uri: str,
    auth: str,
    endpoint: str,
    *,
    job_dir: Path | None = None,
    on_progress: ProgressCallback = None,
) -> dict[str, Any]:
    """按 UPOS 协议分片上传。"""
    total = video_path.stat().st_size
    chunk_count = max(1, math.ceil(total / CHUNK_SIZE))
    upload_id = hashlib.md5(f"{video_path.name}{time.time()}".encode()).hexdigest()[:16]

    _save_progress(job_dir, {
        "status": "uploading",
        "percent": 0,
        "uploaded_bytes": 0,
        "total_bytes": total,
        "chunks_total": chunk_count,
        "chunks_done": 0,
        "message": "开始分片上传",
    })

    uploaded = 0
    with video_path.open("rb") as f:
        for part in range(1, chunk_count + 1):
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            start = uploaded
            end = uploaded + len(chunk) - 1
            put_url = f"https:{endpoint}/{upos_uri}?uploadId={upload_id}&partNumber={part}&chunk={part}&chunks={chunk_count}&size={len(chunk)}&start={start}&end={end}&total={total}"
            headers = {
                "Authorization": auth,
                "X-Upos-Auth": auth,
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(chunk)),
            }
            _http_put_chunk(put_url, chunk, headers)
            uploaded += len(chunk)
            pct = int(uploaded / total * 100)
            msg = f"分片 {part}/{chunk_count} ({pct}%)"
            _save_progress(job_dir, {
                "status": "uploading",
                "percent": pct,
                "uploaded_bytes": uploaded,
                "total_bytes": total,
                "chunks_total": chunk_count,
                "chunks_done": part,
                "message": msg,
            })
            if on_progress:
                on_progress(pct, msg)
            console.print(f"[dim]{msg}[/dim]")

    complete_url = f"https:{endpoint}/{upos_uri}?uploadId={upload_id}&parts={chunk_count}"
    _http_json(complete_url, headers={"Authorization": auth, "X-Upos-Auth": auth}, method="POST")
    return {"upload_id": upload_id, "upos_uri": upos_uri, "size": total}


def upload_video_bilibili(
    video_path: Path,
    title: str,
    description: str,
    cfg: dict[str, Any],
    *,
    job_dir: Path | None = None,
    on_progress: ProgressCallback = None,
) -> dict[str, Any]:
    """B 站开放平台 OAuth + UPOS 分片上传；凭证不全时返回 manifest。"""
    pcfg = (cfg.get("publish") or {}).get("bilibili") or {}
    client_id = pcfg.get("client_id") or pcfg.get("access_key", "")
    client_secret = pcfg.get("client_secret") or pcfg.get("secret", "")
    refresh_token = pcfg.get("refresh_token", "")

    if not video_path.exists():
        return {"ok": False, "error": f"视频不存在: {video_path}"}

    manifest: dict[str, Any] = {
        "platform": "bilibili",
        "video": str(video_path),
        "title": title[:80],
        "description": description[:2000],
        "status": "ready",
    }

    if not client_id or not client_secret or not refresh_token:
        manifest["note"] = "请配置 publish.bilibili.client_id / client_secret / refresh_token"
        manifest["manual_steps"] = [
            "1. 打开 https://member.bilibili.com/platform/upload/video/frame",
            "2. 上传视频文件",
            "3. 粘贴 title 与 description",
        ]
        return manifest

    try:
        token_data = get_access_token(client_id, client_secret, refresh_token)
        access_token = token_data.get("access_token", "")
        if not access_token:
            manifest["error"] = "获取 access_token 失败"
            manifest["token_response"] = token_data
            return manifest

        file_size = video_path.stat().st_size
        _save_progress(job_dir, {"status": "init", "percent": 0, "message": "初始化上传"})

        pre = _init_preupload(access_token, video_path.name, file_size)
        upos_uri = pre.get("upos_uri") or pre.get("url", "")
        auth = pre.get("auth", "")
        endpoint = pre.get("endpoint", "//upos-sz-mirrorcos.bilivideo.com")

        if not upos_uri or not auth:
            manifest["status"] = "upload_prepared"
            manifest["upload_meta"] = {"preupload": pre, "file_size": file_size}
            manifest["note"] = "preupload 未返回 upos_uri，请检查应用权限"
            return manifest

        upload_result = _upload_chunks_upos(
            video_path, upos_uri, auth, endpoint,
            job_dir=job_dir, on_progress=on_progress,
        )

        submit_data = {
            "access_token": access_token,
            "title": title[:80],
            "desc": description[:2000],
            "filename": video_path.name,
            "file_size": str(file_size),
            "upos_uri": upos_uri,
        }
        try:
            submit_resp = _http_json(BILI_UPLOAD_INIT, submit_data, method="POST")
        except urllib.error.HTTPError as e:
            submit_resp = {"http_error": e.code, "note": "分片已完成，稿件提交需应用级 arcopen 权限"}

        _save_progress(job_dir, {
            "status": "done",
            "percent": 100,
            "message": "上传完成",
            "upload_result": upload_result,
            "submit": submit_resp,
        })

        manifest["status"] = "uploaded"
        manifest["upload_result"] = upload_result
        manifest["submit"] = submit_resp
        console.print("[green]B站分片上传完成[/green]")
        return {"ok": True, **manifest}
    except Exception as e:
        _save_progress(job_dir, {"status": "error", "percent": 0, "message": str(e)})
        manifest["error"] = str(e)
        manifest["note"] = "自动上传失败，请使用 manifest 手动上传"
        return manifest


def load_upload_progress(job_dir: Path) -> dict[str, Any] | None:
    path = job_dir / "bilibili_upload_progress.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
