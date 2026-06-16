#!/usr/bin/env python3
"""Web 控制台：上传、任务管理、配置编辑、文案预览。"""

from __future__ import annotations

import json
import mimetypes
import threading
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, File, Form, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from starlette.requests import Request as StarletteRequest

from src.config_io import export_config_bundle, import_config_bundle
from src.health import check_health
from src.job_logger import read_job_log
from src.bilibili_upload import load_upload_progress, retry_upload_bilibili
from src.optional_deps import check_optional, install_optional
from src.setup_wizard import get_setup_checklist
from src.waveform import extract_waveform_peaks
from src.resume_from import suggest_resume_step
from src.ws_hub import broadcast_sync, register, unregister
from src.config_loader import ROOT, load_config, output_dir, save_config
from src.dub_ab import run_dub_ab_comparison
from src.ffmpeg_installer import FFMPEG_ESSENTIALS_URL, ZIP_CACHE, install_ffmpeg, is_ffmpeg_ready
from src.job_queue import (
    acquire, cancel_job, configure as configure_queue, enqueue, pause_queue,
    release, resume_queue, set_priority, status as queue_status,
)
from src.audit_log import audit, read_audit
from src.rate_limit import check_rate_limit
from src.timing_stats import load_timing_stats
from src.prompt_templates import list_templates, get_template, save_template, apply_template_to_cfg
from src.account_matrix import load_accounts, save_accounts
from src.job_backup import backup_job, restore_job
from src.publish_schedule import save_schedule, list_pending_schedules, list_all_schedules, cancel_schedule
from src.publish_scheduler import start_scheduler, run_due_schedules
from src.timing_aggregate import aggregate_job_timings
from src.batch_report import build_batch_report, export_batch_report_html
from src.rag_copy import list_documents, save_document
from src.config_schema import validate_config
from src.vertical_templates import list_vertical_templates
from src.job_cancel import request_cancel, clear_cancel, is_cancel_requested
from src.video_qc import analyze_video
from src.job_subprocess import start_pipeline_subprocess, terminate_pipeline, is_running as subprocess_running
from src.job_compare import compare_jobs
from src.ab_feedback import load_feedback, record_feedback, suggest_from_feedback
from src.browser_publish import run_browser_publish
from src.template_market import list_market_templates, apply_market_template
from src.dashboard_data import build_dashboard
from src.team_auth import load_team_tokens, create_token, verify_team_token
from src.publish_preflight import run_publish_preflight
from src.rag_embed import build_index as build_rag_index
from src.redis_queue import start_redis_worker, enqueue_redis
from src.offline_mode import lm_studio_reachable, apply_offline_fallback
from src.bilibili_oauth import build_authorize_url, exchange_code, save_tokens, load_tokens, refresh_stored_tokens
from src.plugins_user import discover_user_plugins
from src.notifications import notify_job_event
from src.lm_usage import estimate_cost, load_stats
from src.pipeline import run_pipeline
from src.presets import list_presets
from src.preflight import run_preflight
from src.scene_detect import detect_scene_changes
from src.audio_enhance import apply_audio_enhance
from src.pipeline_viz import pipeline_dag_json, webhook_trigger
from src.config_wizard import build_wizard_template, apply_wizard_answers
from src.publish_analytics import analytics_summary, record_analytics
from src.cloud_storage import upload_job_output
from src.finetune_deep import check_bridge_ready, export_feedback_for_training
from src.subtitle_editor import (
    delete_segment, load_subtitle_segments, merge_segments,
    save_subtitle_segments, split_segment, update_segment_text, update_segment_time,
)
from src.video_player import generate_hls, generate_thumbnail
from src.persistence import list_jobs as db_list_jobs, step_timing_aggregate
from src.job_index import job_created, job_done, job_failed, job_running, list_indexed_jobs
from src.platform_stats import sync_all_jobs, sync_job_stats
from src.sensitive_report import build_compliance_report
from src.batch_dag import load_batch_plan, next_runnable, save_batch_plan, batch_plan_from_watch, BatchNode
from src.vertical_series import export_series_pack, plan_vertical_series
from src.subtitle_collab import acquire_lock, release_lock, list_locks
from src.compare_player import list_video_variants
from src.video_player import generate_thumbnails_sprite
from src.tenant import resolve_output_dir
from src.progress_tracker import load_progress
from src.publish_pack import build_publish_pack, save_segments_and_srt
from src.service_checks import check_gpt_sovits, check_lm_studio_detail
from src.terminology import load_terminology, save_terminology, terminology_path

WEB_DIR = ROOT / "web"
STATIC_DIR = WEB_DIR / "static"
APP_VERSION = "3.9.0"
LATEST_VERSION_URL = "https://raw.githubusercontent.com/180024421/video-promo-pipeline/main/VERSION"

ASSETS_DIR = ROOT / "assets"

_tenant_ctx = threading.local()


def _current_tenant() -> str:
    return getattr(_tenant_ctx, "id", "") or ""


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        _tenant_ctx.id = request.headers.get("X-Tenant-ID", "") or request.query_params.get("tenant", "")
        return await call_next(request)


app = FastAPI(title="video-promo-pipeline", version=APP_VERSION)
app.add_middleware(TenantMiddleware)
_cfg = load_config()
_jobs_lock = threading.Lock()
_running: dict[str, dict[str, Any]] = {}
_ffmpeg_install: dict[str, Any] = {"status": "idle", "message": "", "progress": 0}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        cfg = load_config()
        path = request.url.path
        rl_cfg = cfg.get("rate_limit") or {}
        if rl_cfg.get("enabled", False) and path.startswith("/api/"):
            client = request.client.host if request.client else "unknown"
            ok, msg = check_rate_limit(client, max_per_minute=int(rl_cfg.get("max_per_minute", 120)))
            if not ok:
                return JSONResponse({"error": msg}, status_code=429)
        token = (cfg.get("web") or {}).get("auth_token", "")
        if token and path.startswith("/api/") and path not in ("/api/status", "/api/health", "/api/version"):
            hdr = request.headers.get("X-Auth-Token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
            q = request.query_params.get("token", "")
            if hdr != token and q != token:
                return JSONResponse({"error": "未授权，请设置 X-Auth-Token"}, status_code=401)
        if token and path.startswith("/ws/"):
            q = request.query_params.get("token", "")
            if q != token:
                return JSONResponse({"error": "未授权 WebSocket"}, status_code=401)
        response = await call_next(request)
        if path.startswith("/api/") and request.method != "GET":
            audit(f"{request.method} {path}", {"status": response.status_code})
        return response


app.add_middleware(AuthMiddleware)


def _reload_cfg() -> dict[str, Any]:
    global _cfg
    _cfg = load_config()
    return _cfg


def _output_base() -> Path:
    tcfg = _cfg.get("tenant") or {}
    tid = _current_tenant()
    if tcfg.get("enabled") and tid:
        return resolve_output_dir(_cfg, tid)
    return ROOT / _cfg.get("output", {}).get("dir", "output")


def _safe_job_path(job_name: str) -> Path | None:
    base = _output_base().resolve()
    target = (base / job_name).resolve()
    if not str(target).startswith(str(base)) or not target.is_dir():
        return None
    return target


def _job_files(job_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for p in sorted(job_dir.iterdir()):
        if not p.is_file():
            continue
        files.append({
            "name": p.name,
            "size": p.stat().st_size,
            "ext": p.suffix.lower(),
            "type": _file_type(p),
        })
    return files


def _file_type(p: Path) -> str:
    ext = p.suffix.lower()
    if ext in {".mp4", ".mkv", ".mov", ".webm"}:
        return "video"
    if ext in {".srt", ".vtt", ".ass"}:
        return "subtitle"
    if ext in {".txt", ".md"}:
        return "text"
    if ext == ".json":
        return "json"
    if ext == ".zip":
        return "archive"
    if ext == ".png":
        return "image"
    return "other"


def _read_text_safe(path: Path, limit: int = 50000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        return text[:limit]
    except Exception:
        return ""


def _list_jobs() -> list[dict]:
    base = _output_base()
    if not base.exists():
        return []
    jobs: list[dict] = []
    for d in sorted(base.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        summary_path = d / "summary.json"
        item: dict[str, Any] = {
            "name": d.name,
            "path": str(d),
            "mtime": d.stat().st_mtime,
            "created": datetime.fromtimestamp(d.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "files": _job_files(d),
        }
        if summary_path.exists():
            try:
                item["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        promo = d / "promo_copy.json"
        if promo.exists():
            try:
                item["promo"] = json.loads(promo.read_text(encoding="utf-8"))
            except Exception:
                pass
        with _jobs_lock:
            run_info = _running.get(d.name, {})
            item["status"] = run_info.get("status", "idle")
            item["error"] = run_info.get("error", "")
            item["step"] = run_info.get("step", "")
            item["progress"] = run_info.get("progress", 0)
        prog = load_progress(d)
        if prog:
            item["pipeline_progress"] = prog
            if run_info.get("status") != "running":
                item["progress"] = prog.get("progress", item["progress"])
        jobs.append(item)
    return jobs


def _job_detail(job_name: str) -> dict[str, Any] | None:
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return None
    detail: dict[str, Any] = {
        "name": job_name,
        "path": str(job_dir),
        "files": _job_files(job_dir),
    }
    for fname in ("summary.json", "promo_copy.json", "segments.json", "narration.json", "clip_short.json", "transcribe_progress.json"):
        fp = job_dir / fname
        if fp.exists():
            try:
                detail[fname.replace(".json", "")] = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                pass
    for fname in ("transcript.txt", "promo_copy.md", "bilibili_description.txt", "xiaohongshu_post.txt"):
        fp = job_dir / fname
        if fp.exists():
            detail[fname.replace(".", "_")] = _read_text_safe(fp)
    with _jobs_lock:
        run_info = _running.get(job_name, {})
        detail["status"] = run_info.get("status", "idle")
        detail["error"] = run_info.get("error", "")
        detail["step"] = run_info.get("step", "")
        detail["progress"] = run_info.get("progress", 0)
    prog = load_progress(job_dir)
    if prog:
        detail["pipeline_progress"] = prog
    return detail


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = WEB_DIR / "index.html"
    html = html_path.read_text(encoding="utf-8")
    html = html.replace("/static/style.css", f"/static/style.css?v={APP_VERSION}")
    html = html.replace("/static/app.js", f"/static/app.js?v={APP_VERSION}")
    html = html.replace("/static/v39.js", f"/static/v39.js?v={APP_VERSION}")
    return HTMLResponse(html)


@app.get("/api/finetune-bridge")
def api_finetune_bridge():
    from src.finetune_bridge import bridge_summary
    return JSONResponse(bridge_summary())


@app.get("/api/health")
def api_health():
    return JSONResponse(check_health(load_config()))


@app.get("/api/setup-wizard")
def api_setup_wizard():
    return JSONResponse(get_setup_checklist(load_config()))


@app.get("/api/optional-deps")
def api_optional_deps():
    return JSONResponse({"packages": check_optional()})


@app.post("/api/optional-deps/install")
async def api_optional_install(request: Request):
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    keys = body.get("packages") or list(check_optional().keys())
    return JSONResponse(install_optional(keys))


@app.get("/api/jobs/{job_name}/waveform")
def api_job_waveform(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    summary_path = job_dir / "summary.json"
    video = None
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        for key in ("work_video", "final_video", "source_video"):
            p = summary.get(key)
            if p and Path(str(p)).exists():
                video = Path(str(p))
                break
    if not video:
        video = next((p for p in job_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv"}), None)
    if not video:
        return JSONResponse({"error": "无视频"}, status_code=404)
    cfg = load_config()
    data = extract_waveform_peaks(video, cfg)
    segs_path = job_dir / "segments.json"
    if segs_path.exists():
        data["segments"] = json.loads(segs_path.read_text(encoding="utf-8")).get("segments", [])
    return JSONResponse(data)


@app.post("/api/jobs/{job_name}/bilibili-retry")
def api_bilibili_retry(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)

    def _run(cb):
        retry_upload_bilibili(job_dir, load_config())

    _run_job_async(job_name, _run)
    return JSONResponse({"ok": True})


@app.get("/api/version")
def api_version():
    latest = APP_VERSION
    if (ROOT / "VERSION").exists():
        latest = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    update_available = latest > APP_VERSION
    if LATEST_VERSION_URL:
        try:
            with urllib.request.urlopen(LATEST_VERSION_URL, timeout=3) as resp:
                remote = resp.read().decode().strip()
                if remote:
                    latest = remote
                    update_available = remote > APP_VERSION
        except Exception:
            pass
    return JSONResponse({
        "version": APP_VERSION,
        "latest": latest,
        "update_available": update_available,
    })


@app.get("/api/config/export")
def api_config_export():
    path = export_config_bundle()
    return FileResponse(path, media_type="application/x-yaml", filename=path.name)


@app.post("/api/config/import")
async def api_config_import(request: Request, merge: str = "true"):
    body = await request.body()
    tmp = ROOT / "output" / "_config_import.yaml"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(body)
    data = import_config_bundle(tmp, merge=merge.lower() != "false")
    _reload_cfg()
    return JSONResponse({"ok": True, "keys": list(data.keys())})


@app.get("/api/batch/watch")
def api_batch_watch():
    cfg = load_config()
    watch = ROOT / (cfg.get("batch") or {}).get("watch_dir", "watch_in")
    patterns = (cfg.get("batch") or {}).get("file_patterns", ["*.mp4", "*.mkv", "*.mov", "*.webm"])
    pending: list[dict[str, Any]] = []
    if watch.exists():
        seen: set[str] = set()
        for pat in patterns:
            for p in watch.glob(pat):
                if p.name in seen:
                    continue
                seen.add(p.name)
                pending.append({
                    "name": p.name,
                    "size": p.stat().st_size,
                    "path": str(p),
                    "mtime": p.stat().st_mtime,
                })
    pending.sort(key=lambda x: x["mtime"], reverse=True)
    return JSONResponse({"watch_dir": str(watch), "pending": pending, "count": len(pending)})


@app.post("/api/batch/process")
def api_batch_process():
    cfg = load_config()
    watch = ROOT / (cfg.get("batch") or {}).get("watch_dir", "watch_in")
    if not watch.exists():
        return JSONResponse({"error": "watch_in 目录不存在"}, status_code=400)
    started: list[str] = []
    for p in sorted(watch.glob("*.mp4"), key=lambda x: x.stat().st_mtime):
        job_name = f"{p.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        job_dir = output_dir(cfg, job_name)

        def _make_run(dest: Path, jd: Path, jn: str):
            def _run(on_step):
                run_pipeline(dest, job_dir=jd, on_step=on_step)
            return _run

        _run_job_async(job_name, _make_run(p, job_dir, job_name))
        started.append(job_name)
        break  # 一次处理一个，其余排队
    return JSONResponse({"ok": True, "started": started})


@app.websocket("/ws/progress")
async def ws_progress(websocket: WebSocket):
    await websocket.accept()
    await register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await unregister(websocket)


@app.get("/api/jobs/{job_name}/upload-progress")
def api_upload_progress(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    prog = load_upload_progress(job_dir)
    return JSONResponse(prog or {"status": "none"})


@app.get("/api/status")
def api_status():
    _reload_cfg()
    checks: dict[str, Any] = {}
    import shutil
    checks["ffmpeg"] = is_ffmpeg_ready(_cfg)
    ffmpeg_path = ""
    if checks["ffmpeg"]:
        ffmpeg_path = (_cfg.get("ffmpeg") or {}).get("path") or shutil.which("ffmpeg") or ""
        bundled = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
        if not ffmpeg_path and bundled.exists():
            ffmpeg_path = str(bundled)
    checks["ffmpeg_path"] = ffmpeg_path
    checks["auto_editor"] = shutil.which("auto-editor") is not None
    try:
        import faster_whisper  # noqa: F401
        checks["whisper"] = True
    except ImportError:
        checks["whisper"] = False
    try:
        import edge_tts  # noqa: F401
        checks["edge_tts"] = True
    except ImportError:
        checks["edge_tts"] = False
    lm_ok = False
    lm_models: list[str] = []
    lcfg = _cfg.get("lm_studio") or {}
    if lcfg.get("enabled", True):
        base = lcfg.get("base_url", "http://127.0.0.1:1234/v1").rstrip("/").removesuffix("/v1")
        try:
            with urllib.request.urlopen(f"{base}/v1/models", timeout=3) as resp:
                if resp.status == 200:
                    lm_ok = True
                    data = json.loads(resp.read().decode())
                    lm_models = [m.get("id", "") for m in data.get("data", [])]
        except Exception:
            pass
    checks["lm_studio"] = lm_ok
    checks["lm_models"] = lm_models
    checks["lm_detail"] = check_lm_studio_detail(_cfg)
    dub_engine = (_cfg.get("dubbing") or {}).get("engine", "edge-tts")
    if dub_engine == "gpt-sovits":
        checks["gpt_sovits"] = check_gpt_sovits(_cfg)
    else:
        checks["gpt_sovits"] = {"ok": None, "skipped": True}
    checks["queue"] = queue_status()
    checks["ffmpeg_hint"] = FFMPEG_ESSENTIALS_URL
    with _jobs_lock:
        checks["ffmpeg_install"] = dict(_ffmpeg_install)
    return JSONResponse({
        "ok": checks["ffmpeg"] and checks["whisper"],
        "version": APP_VERSION,
        "checks": checks,
        "config_path": str(ROOT / "config.yaml"),
        "jobs_count": len(_list_jobs()),
        "lm_usage": {**load_stats(), "cost": estimate_cost()},
    })


@app.get("/api/ffmpeg/download-zip")
def api_ffmpeg_download_zip():
    """浏览器直接下载 FFmpeg 安装包（优先本地缓存，否则跳转官方）。"""
    if ZIP_CACHE.exists():
        return FileResponse(
            ZIP_CACHE,
            media_type="application/zip",
            filename="ffmpeg-release-essentials.zip",
        )
    return RedirectResponse(url=FFMPEG_ESSENTIALS_URL)


@app.get("/api/ffmpeg/install-status")
def api_ffmpeg_install_status():
    with _jobs_lock:
        return JSONResponse(dict(_ffmpeg_install))


@app.post("/api/ffmpeg/install")
def api_ffmpeg_install():
    """一键下载、解压并写入 config.yaml。"""
    global _cfg
    with _jobs_lock:
        if _ffmpeg_install.get("status") == "running":
            return JSONResponse({"error": "正在安装中，请稍候"}, status_code=409)

    def _progress(msg: str, pct: int) -> None:
        with _jobs_lock:
            _ffmpeg_install.update({"status": "running", "message": msg, "progress": pct})

    def _run() -> None:
        global _cfg
        try:
            with _jobs_lock:
                _ffmpeg_install.update({"status": "running", "message": "准备中…", "progress": 0})
            result = install_ffmpeg(_progress)
            _reload_cfg()
            with _jobs_lock:
                _ffmpeg_install.update({
                    "status": "done",
                    "message": "安装完成",
                    "progress": 100,
                    "path": result.get("path"),
                })
        except Exception as e:
            with _jobs_lock:
                _ffmpeg_install.update({"status": "error", "message": str(e), "progress": 0})

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"ok": True})


@app.get("/api/config")
def api_get_config():
    return JSONResponse(load_config())


@app.post("/api/config")
async def api_save_config(request: Request):
    try:
        request_body = await request.json()
        path = save_config(request_body)
        _reload_cfg()
        return JSONResponse({"ok": True, "path": str(path)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/jobs")
def api_jobs():
    return JSONResponse(_list_jobs())


@app.get("/api/jobs/{job_name}")
def api_job_detail(job_name: str):
    detail = _job_detail(job_name)
    if not detail:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return JSONResponse(detail)


@app.get("/api/jobs/{job_name}/files/{filepath:path}")
def api_job_file(job_name: str, filepath: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    fp = (job_dir / filepath).resolve()
    if not str(fp).startswith(str(job_dir.resolve())) or not fp.is_file():
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    ext = fp.suffix.lower()
    mime_map = {".m3u8": "application/vnd.apple.mpegurl", ".ts": "video/mp2t"}
    mime = mime_map.get(ext) or mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
    return FileResponse(fp, media_type=mime, filename=fp.name)


@app.get("/api/presets")
def api_presets():
    return JSONResponse(list_presets())


def _run_job_async(job_name: str, fn=None, *, spec: dict[str, Any] | None = None) -> int:
    pos = enqueue(job_name)
    with _jobs_lock:
        _running[job_name] = {"status": "queued", "step": f"排队中 (#{pos})", "progress": 0, "queue_position": pos}

    def _run():
        def on_wait(position: int) -> None:
            with _jobs_lock:
                _running[job_name] = {
                    "status": "queued",
                    "step": f"排队中 (#{position})",
                    "progress": 0,
                    "queue_position": position,
                }

        try:
            acquire(job_name, on_wait=on_wait)
        except Exception as e:
            with _jobs_lock:
                _running[job_name] = {"status": "error", "error": str(e), "step": "排队失败", "progress": 0}
            clear_cancel(job_name)
            return

        clear_cancel(job_name)
        with _jobs_lock:
            _running[job_name] = {"status": "running", "step": "初始化", "progress": 0}
        try:
            job_running(job_name, "初始化")
        except Exception:
            pass
        try:
            def on_step(step: str):
                with _jobs_lock:
                    from src.pipeline import STEPS
                    try:
                        idx = STEPS.index(step) if step in STEPS else 0
                    except ValueError:
                        idx = 0
                    pct = int((idx + 1) / max(len(STEPS), 1) * 100) if step != "完成" else 100
                    state = {"status": "running", "step": step, "progress": pct, "job": job_name}
                    _running[job_name] = state
                broadcast_sync({"type": "job_progress", **state})

            cfg = load_config()
            use_sub = (cfg.get("web") or {}).get("use_subprocess_pipeline", True) and spec is not None
            if use_sub:
                from src.job_cancel import check_cancel
                proc = start_pipeline_subprocess(job_name, spec)
                try:
                    while proc.is_alive():
                        check_cancel(job_name)
                        prog = load_progress(Path(spec["job_dir"])) if spec.get("job_dir") else {}
                        on_step(prog.get("current") or "处理中")
                        proc.join(timeout=1.0)
                except RuntimeError:
                    terminate_pipeline(job_name)
                    raise
                if proc.exitcode not in (0, None):
                    if proc.exitcode < 0 or is_cancel_requested(job_name):
                        raise RuntimeError("任务已取消")
                    raise RuntimeError(f"子进程退出码 {proc.exitcode}")
            else:
                fn(on_step)
            with _jobs_lock:
                state = {"status": "done", "step": "完成", "progress": 100, "job": job_name}
                _running[job_name] = state
            try:
                job_done(job_name)
            except Exception:
                pass
            broadcast_sync({"type": "job_progress", **state})
        except Exception as e:
            with _jobs_lock:
                cancelled = str(e) == "任务已取消"
                state = {
                    "status": "error",
                    "error": str(e),
                    "step": "已取消" if cancelled else "失败",
                    "progress": 0,
                    "job": job_name,
                }
                _running[job_name] = state
            try:
                if not cancelled:
                    job_failed(job_name, str(e))
            except Exception:
                pass
            broadcast_sync({"type": "job_progress", **state})
            if not cancelled:
                notify_job_event("job_error", job_name, {"error": str(e)}, load_config())
        finally:
            clear_cancel(job_name)
            release(job_name)

    threading.Thread(target=_run, daemon=True).start()
    return pos


@app.post("/api/jobs/{job_name}/rerun/{step}")
def api_rerun_step(job_name: str, step: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    raw = next((p for p in job_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv", ".mov"} and "_subtitled" not in p.stem and "_short_" not in p.stem and "_dubbed" not in p.stem and "_smart" not in p.stem and "_broll" not in p.stem), None)
    if not raw and step not in ("copy", "pack"):
        raw = job_dir

    kwargs = {"job_dir": job_dir, "force": True}
    if step == "copy":
        _run_job_async(job_name, lambda cb: run_pipeline(job_dir, only_copy=True, job_dir=job_dir, on_step=cb))
    elif step == "dub":
        _run_job_async(job_name, lambda cb: run_pipeline(raw or job_dir, only_dub=True, on_step=cb, **kwargs))
    elif step == "burn":
        _run_job_async(job_name, lambda cb: run_pipeline(raw or job_dir, only_burn=True, on_step=cb, **kwargs))
    elif step == "short":
        _run_job_async(job_name, lambda cb: run_pipeline(raw or job_dir, only_short=True, on_step=cb, **kwargs))
    elif step == "pack":
        _run_job_async(job_name, lambda cb: run_pipeline(job_dir, only_pack=True, job_dir=job_dir, on_step=cb))
    elif step in ("transcribe", "cut", "smart"):
        kwargs = {"job_dir": job_dir, "force": True, "from_step": step}
        raw_vid = raw or job_dir
        _run_job_async(job_name, lambda cb: run_pipeline(raw_vid, on_step=cb, **kwargs))
    elif step == "resume":
        prog = load_progress(job_dir)
        suggested = suggest_resume_step(prog) or "transcribe"
        kwargs = {"job_dir": job_dir, "force": True, "from_step": suggested}
        raw_vid = raw or job_dir
        _run_job_async(job_name, lambda cb: run_pipeline(raw_vid, on_step=cb, **kwargs))
    return JSONResponse({"ok": True})


@app.put("/api/jobs/{job_name}/narration")
async def api_save_narration(job_name: str, request: Request):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    body = await request.json()
    (job_dir / "narration.json").write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSONResponse({"ok": True})


@app.get("/api/jobs/{job_name}/download.zip")
def api_download_zip(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    from src.export_pack import pack_job_zip
    z = pack_job_zip(job_dir, load_config())
    if not z or not z.exists():
        return JSONResponse({"error": "打包失败"}, status_code=500)
    return FileResponse(z, media_type="application/zip", filename=z.name)


@app.post("/api/jobs/{job_name}/regenerate-copy")
def api_regenerate_copy(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    if not (job_dir / "transcript.txt").exists():
        return JSONResponse({"error": "缺少 transcript.txt"}, status_code=400)
    _run_job_async(job_name, lambda cb: run_pipeline(job_dir, only_copy=True, job_dir=job_dir, on_step=cb))
    return JSONResponse({"ok": True})


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    skip_cut: str = Form(""),
    skip_burn: str = Form(""),
    skip_copy: str = Form(""),
    skip_dub: str = Form(""),
    preset: str = Form(""),
    only_transcribe: str = Form(""),
    force_start: str = Form(""),
    persona: str = Form(""),
    topic: str = Form(""),
    keywords: str = Form(""),
    platforms: str = Form(""),
):
    if not file.filename:
        return JSONResponse({"error": "无文件名"}, status_code=400)

    _reload_cfg()
    if not is_ffmpeg_ready(_cfg):
        return JSONResponse({
            "error": "FFmpeg 未就绪，请先在仪表盘「一键下载并安装」",
        }, status_code=400)

    lcfg = _cfg.get("lm_studio") or {}
    lm_needed = not skip_copy and not only_transcribe
    lm_ok = check_lm_studio_detail(_cfg).get("ok", False)
    warnings: list[str] = []
    if lm_needed and lcfg.get("enabled", True) and not lm_ok and not force_start:
        return JSONResponse({
            "error": "LM Studio 未连接。可勾选「仅转写」或「跳过文案」，或确认 LM 已启动后重试",
            "lm_required": True,
        }, status_code=400)
    if lm_needed and not lm_ok:
        warnings.append("LM Studio 未连接，文案/智能剪辑可能失败")

    upload_dir = ROOT / "watch_in"
    upload_dir.mkdir(exist_ok=True)
    dest = upload_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)

    cfg_override: dict[str, Any] = {}
    if persona or topic or keywords or platforms:
        copy_override: dict[str, Any] = {}
        for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
            copy_override[p] = {}
        if persona:
            for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
                copy_override[p]["persona"] = persona
        if topic:
            for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
                copy_override[p]["content_type"] = topic
        if keywords:
            kw = [k.strip() for k in keywords.split(",") if k.strip()]
            for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
                copy_override[p]["keywords"] = kw
        if platforms:
            enabled = {p.strip().lower() for p in platforms.split(",")}
            for p in ("bilibili", "xiaohongshu", "douyin", "wechat_mp"):
                copy_override[p]["enabled"] = p in enabled
        cfg_override["copy"] = copy_override

    job_name = f"{dest.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    job_dir = output_dir(_cfg, job_name)
    try:
        job_created(job_name)
    except Exception:
        pass

    spec = {
        "job_name": job_name,
        "video_path": str(dest),
        "job_dir": str(job_dir),
        "skip_cut": bool(skip_cut),
        "skip_burn": bool(skip_burn),
        "skip_copy": bool(skip_copy),
        "skip_dub": bool(skip_dub),
        "only_transcribe": bool(only_transcribe),
        "preset": preset or None,
        "cfg_override": cfg_override or None,
    }

    def _run(on_step):
        run_pipeline(
            dest, job_dir=job_dir, skip_cut=bool(skip_cut), skip_burn=bool(skip_burn),
            skip_copy=bool(skip_copy), skip_dub=bool(skip_dub), only_transcribe=bool(only_transcribe),
            preset=preset or None, cfg_override=cfg_override or None, on_step=on_step,
        )

    pos = _run_job_async(job_name, _run, spec=spec)
    return JSONResponse({"ok": True, "job": job_name, "job_dir": str(job_dir), "warnings": warnings, "queue_position": pos})


@app.delete("/api/jobs/{job_name}")
def api_delete_job(job_name: str):
    _reload_cfg()
    if not (_cfg.get("web") or {}).get("enable_delete", True):
        return JSONResponse({"error": "删除功能未启用"}, status_code=403)
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    import shutil
    shutil.rmtree(job_dir, ignore_errors=True)
    with _jobs_lock:
        _running.pop(job_name, None)
    return JSONResponse({"ok": True})


@app.put("/api/jobs/{job_name}/segments")
async def api_save_segments(job_name: str, request: Request):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    body = await request.json()
    segments = body.get("segments") or body
    if not isinstance(segments, list):
        return JSONResponse({"error": "无效 segments"}, status_code=400)
    cfg = load_config()
    save_segments_and_srt(job_dir, segments, cfg)
    return JSONResponse({"ok": True})


@app.get("/api/jobs/{job_name}/logs")
def api_job_logs(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    text = read_job_log(job_dir)
    err = job_dir / "error.log"
    if err.exists():
        text += "\n--- error.log ---\n" + err.read_text(encoding="utf-8", errors="replace")
    return JSONResponse({"logs": text, "source": "job.log"})


@app.get("/api/jobs/{job_name}/publish-pack")
def api_publish_pack(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    pack = build_publish_pack(job_dir, load_config())
    return JSONResponse(pack)


@app.get("/api/terminology")
def api_get_terminology():
    cfg = load_config()
    reps = load_terminology(cfg)
    return JSONResponse({"path": str(terminology_path(cfg)), "replacements": reps})


@app.post("/api/terminology")
async def api_save_terminology(request: Request):
    body = await request.json()
    reps = body.get("replacements") or {}
    cfg = load_config()
    path = save_terminology({str(k): str(v) for k, v in reps.items()}, cfg)
    return JSONResponse({"ok": True, "path": str(path)})


@app.post("/api/assets/upload")
async def api_assets_upload(
    file: UploadFile = File(...),
    kind: str = Form("bgm"),
):
    if not file.filename:
        return JSONResponse({"error": "无文件名"}, status_code=400)
    sub = {"bgm": "bgm", "voice": "voice", "broll": "broll"}.get(kind, "misc")
    dest_dir = ASSETS_DIR / sub
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file.filename
    dest.write_bytes(await file.read())
    rel = str(dest.relative_to(ROOT)).replace("\\", "/")
    return JSONResponse({"ok": True, "path": rel, "absolute": str(dest)})


@app.get("/api/assets")
def api_list_assets():
    items: list[dict[str, Any]] = []
    if ASSETS_DIR.exists():
        for p in ASSETS_DIR.rglob("*"):
            if p.is_file() and p.name != ".gitkeep":
                items.append({
                    "name": p.name,
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "kind": p.parent.name,
                    "size": p.stat().st_size,
                })
    return JSONResponse(items)


@app.post("/api/tts/test")
async def api_tts_test(request: Request):
    body = await request.json()
    text = body.get("text", "你好，这是配音测试。")
    engine = body.get("engine") or (_cfg.get("dubbing") or {}).get("engine", "edge-tts")
    out_dir = ROOT / "output" / "_tts_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp3 = out_dir / "test.mp3"
    cfg = load_config()
    try:
        if engine == "edge-tts":
            import edge_tts
            voice = body.get("voice") or (cfg.get("dubbing") or {}).get("voice", "zh-CN-YunxiNeural")
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(out_mp3))
        elif engine == "gpt-sovits":
            return JSONResponse({"ok": False, "error": "GPT-SoVITS 试播请确保服务运行，并使用任务内配音重跑"})
        else:
            return JSONResponse({"ok": False, "error": f"暂不支持试播引擎: {engine}"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return FileResponse(out_mp3, media_type="audio/mpeg", filename="test.mp3")


@app.get("/api/lm-usage")
def api_lm_usage():
    s = load_stats()
    return JSONResponse({**s, "cost": estimate_cost(s)})


@app.get("/api/jobs/{job_name}/vision-plan")
def api_vision_plan(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    pending = job_dir / "vision_clip_plan_pending.json"
    confirmed = job_dir / "vision_confirmed.json"
    data = None
    if pending.exists():
        data = json.loads(pending.read_text(encoding="utf-8"))
    return JSONResponse({"pending": data, "confirmed": confirmed.exists()})


@app.post("/api/jobs/{job_name}/vision-approve")
def api_vision_approve(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    pending = job_dir / "vision_clip_plan_pending.json"
    if not pending.exists():
        return JSONResponse({"error": "无待确认视觉方案"}, status_code=400)
    plan = json.loads(pending.read_text(encoding="utf-8"))
    (job_dir / "vision_confirmed.json").write_text(json.dumps({"approved": True, "clips": plan.get("clips", [])}, ensure_ascii=False, indent=2), encoding="utf-8")
    pending.write_text(json.dumps({**plan, "status": "approved"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSONResponse({"ok": True})


@app.post("/api/jobs/{job_name}/dub-ab")
def api_dub_ab(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    narr_path = job_dir / "narration.json"
    if not narr_path.exists():
        return JSONResponse({"error": "缺少 narration.json"}, status_code=400)
    narration = json.loads(narr_path.read_text(encoding="utf-8"))
    raw = next((p for p in job_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv"} and "_subtitled" not in p.stem and "_short_" not in p.stem), None)
    if not raw:
        return JSONResponse({"error": "找不到源视频"}, status_code=400)

    def _run(cb):
        run_dub_ab_comparison(raw, narration, load_config(), job_dir)

    _run_job_async(job_name, _run)
    return JSONResponse({"ok": True})


@app.get("/api/queue")
def api_queue():
    return JSONResponse(queue_status())


@app.post("/api/queue/pause")
def api_queue_pause():
    pause_queue()
    return JSONResponse({"ok": True})


@app.post("/api/queue/resume")
def api_queue_resume():
    resume_queue()
    return JSONResponse({"ok": True})


@app.post("/api/queue/cancel/{job_name}")
def api_queue_cancel(job_name: str):
    cancel_job(job_name)
    request_cancel(job_name)
    return JSONResponse({"ok": True})


@app.post("/api/queue/force-stop/{job_name}")
def api_force_stop(job_name: str):
    cancel_job(job_name)
    request_cancel(job_name)
    terminate_pipeline(job_name)
    with _jobs_lock:
        if job_name in _running:
            _running[job_name] = {"status": "error", "error": "已强制停止", "step": "已取消", "progress": 0}
    return JSONResponse({"ok": True})


@app.post("/api/queue/priority/{job_name}")
async def api_queue_priority(job_name: str, request: Request):
    body = await request.json()
    set_priority(job_name, int(body.get("priority", 0)))
    return JSONResponse({"ok": True})


@app.get("/api/jobs/{job_name}/timing")
def api_job_timing(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return JSONResponse(load_timing_stats(job_dir) or {})


@app.get("/api/prompt-templates")
def api_list_prompt_templates():
    return JSONResponse(list_templates())


@app.get("/api/prompt-templates/{tid}")
def api_get_prompt_template(tid: str):
    t = get_template(tid)
    if not t:
        return JSONResponse({"error": "不存在"}, status_code=404)
    return JSONResponse(t)


@app.post("/api/prompt-templates/{tid}")
async def api_save_prompt_template(tid: str, request: Request):
    body = await request.json()
    p = save_template(tid, body)
    return JSONResponse({"ok": True, "path": str(p)})


@app.get("/api/accounts")
def api_accounts():
    return JSONResponse(load_accounts())


@app.post("/api/accounts")
async def api_save_accounts(request: Request):
    body = await request.json()
    p = save_accounts(body.get("accounts") or body)
    return JSONResponse({"ok": True, "path": str(p)})


@app.get("/api/audit")
def api_audit():
    return JSONResponse(read_audit(300))


@app.get("/api/bilibili/oauth/url")
def api_bili_oauth_url():
    cfg = load_config()
    pcfg = (cfg.get("publish") or {}).get("bilibili") or {}
    redirect = pcfg.get("redirect_uri", "http://127.0.0.1:8766/api/bilibili/oauth/callback")
    url = build_authorize_url(pcfg.get("client_id", ""), redirect)
    tokens = load_tokens()
    return JSONResponse({
        "url": url,
        "authorized": bool(tokens.get("access_token") or tokens.get("refresh_token")),
    })


@app.get("/api/bilibili/oauth/callback")
def api_bili_oauth_callback(code: str = "", state: str = ""):
    cfg = load_config()
    pcfg = (cfg.get("publish") or {}).get("bilibili") or {}
    redirect = pcfg.get("redirect_uri", "http://127.0.0.1:8766/api/bilibili/oauth/callback")
    if not code:
        return JSONResponse({"error": "missing code"}, status_code=400)
    data = exchange_code(pcfg.get("client_id", ""), pcfg.get("client_secret", ""), code, redirect)
    save_tokens(data)
    return JSONResponse({"ok": True, "message": "授权成功，token 已保存"})


@app.post("/api/jobs/{job_name}/schedule")
async def api_schedule_publish(job_name: str, request: Request):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    body = await request.json()
    entry = save_schedule(job_dir, body.get("platform", "bilibili"), body.get("publish_at", ""), load_config())
    return JSONResponse({"ok": True, "entry": entry})


@app.get("/api/schedules/pending")
def api_pending_schedules():
    return JSONResponse(list_pending_schedules(_output_base()))


@app.get("/api/schedules/all")
def api_all_schedules():
    return JSONResponse(list_all_schedules(_output_base()))


@app.post("/api/schedules/cancel")
async def api_cancel_schedule(request: Request):
    body = await request.json()
    job_dir = _safe_job_path(body.get("job_name", ""))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    ok = cancel_schedule(job_dir, body.get("platform", ""), body.get("publish_at", ""))
    return JSONResponse({"ok": ok})


@app.post("/api/schedules/run-now")
def api_run_schedules_now():
    results = run_due_schedules(_output_base(), load_config())
    return JSONResponse({"ok": True, "results": results})


@app.get("/api/analytics/timing")
def api_analytics_timing():
    return JSONResponse(aggregate_job_timings(_output_base()))


@app.get("/api/analytics/lm-cost")
def api_analytics_lm_cost():
    stats = load_stats()
    cost = estimate_cost(stats, load_config())
    return JSONResponse({**stats, **cost})


@app.get("/api/analytics/publish")
def api_publish_analytics():
    return JSONResponse(analytics_summary())


@app.post("/api/analytics/publish")
async def api_record_publish(request: Request):
    body = await request.json()
    r = record_analytics(
        body.get("job", ""),
        body.get("platform", "unknown"),
        **{k: v for k, v in body.items() if k not in ("job", "platform")},
    )
    return JSONResponse(r)


@app.get("/api/pipeline-dag")
def api_pipeline_dag():
    return JSONResponse({"dag": pipeline_dag_json()})


@app.get("/api/finetune-bridge/deep")
def api_finetune_deep():
    return JSONResponse(check_bridge_ready())


@app.post("/api/finetune-bridge/export-feedback")
async def api_export_feedback(request: Request):
    body = await request.json()
    out = ROOT / (body.get("out", "data/finetune_feedback_train.jsonl"))
    r = export_feedback_for_training(out, min_score=float(body.get("min_score", 0.6)))
    return JSONResponse(r)


@app.get("/api/config-wizard")
def api_config_wizard():
    return JSONResponse(build_wizard_template())


@app.post("/api/config-wizard")
async def api_apply_wizard(request: Request):
    body = await request.json()
    answers = body.get("answers", {})
    cfg = load_config()
    new_cfg = apply_wizard_answers(cfg, answers)
    save_config(new_cfg)
    return JSONResponse({"ok": True})


@app.get("/api/jobs/{job_name}/segments")
def api_job_segments(job_name: str):
    job_dir = _safe_job_path(str(job_name))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    segs = load_subtitle_segments(job_dir / "segments.json")
    return JSONResponse({"segments": segs})


@app.put("/api/jobs/{job_name}/segments")
async def api_save_segments(job_name: str, request: Request):
    job_dir = _safe_job_path(str(job_name))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    body = await request.json()
    segs = body.get("segments", [])
    save_subtitle_segments(job_dir / "segments.json", segs)
    return JSONResponse({"ok": True})


@app.put("/api/jobs/{job_name}/segments/{index}/merge/{other}")
def api_merge_segments(job_name: str, index: int, other: int):
    job_dir = _safe_job_path(str(job_name))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    segs = load_subtitle_segments(job_dir / "segments.json")
    segs = merge_segments(index, other, segs)
    save_subtitle_segments(job_dir / "segments.json", segs)
    return JSONResponse({"ok": True})


@app.put("/api/jobs/{job_name}/segments/{index}/split")
async def api_split_segment(job_name: str, index: int, request: Request):
    body = await request.json()
    at_sec = float(body.get("at_sec", 0))
    job_dir = _safe_job_path(str(job_name))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    segs = load_subtitle_segments(job_dir / "segments.json")
    segs = split_segment(index, at_sec, segs)
    save_subtitle_segments(job_dir / "segments.json", segs)
    return JSONResponse({"ok": True})


@app.get("/api/jobs/{job_name}/scenes")
def api_job_scenes(job_name: str, threshold: float = 0.3):
    job_dir = _safe_job_path(str(job_name))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    vid = next((p for p in job_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv", ".mov"}), None)
    if not vid:
        return JSONResponse({"scenes": []})
    scenes = detect_scene_changes(load_config(), vid, threshold=threshold)
    return JSONResponse({"scenes": scenes})


@app.get("/api/jobs/{job_name}/hls")
def api_job_hls(job_name: str):
    job_dir = _safe_job_path(str(job_name))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    vid = next((p for p in job_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv", ".mov"}), None)
    if not vid:
        return JSONResponse({"error": "无视频文件"}, status_code=404)
    hls_dir = job_dir / "hls"
    info = generate_hls(vid, hls_dir)
    return JSONResponse(info)


@app.get("/api/jobs/{job_name}/enhance-audio")
def api_enhance_audio(job_name: str):
    job_dir = _safe_job_path(str(job_name))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    vid = next((p for p in job_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv", ".mov"}), None)
    if not vid:
        return JSONResponse({"error": "无视频文件"}, status_code=404)
    out = job_dir / f"{vid.stem}_enhanced.mp4"
    apply_audio_enhance(load_config(), vid, out)
    return JSONResponse({"ok": True, "output": str(out)})


@app.post("/api/jobs/{job_name}/cloud-upload")
def api_cloud_upload(job_name: str):
    job_dir = _safe_job_path(str(job_name))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    r = upload_job_output(job_dir, load_config())
    return JSONResponse(r)


@app.post("/api/webhook-trigger")
async def api_webhook_trigger(request: Request):
    body = await request.json()
    cfg = load_config()
    r = webhook_trigger(cfg, body)
    if not r.get("ok"):
        return JSONResponse(r, status_code=400)
    video_path = body.get("video_path", "")
    if not video_path or not Path(video_path).exists():
        return JSONResponse({"ok": False, "detail": "video_path 无效"}, status_code=400)
    vp = Path(video_path)
    job_name = body.get("job_name") or f"{vp.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    job_dir = output_dir(cfg, job_name)
    preset = body.get("preset", "")
    try:
        job_created(job_name)
    except Exception:
        pass

    def _run(cb):
        run_pipeline(vp, job_dir=job_dir, preset=preset or None, on_step=cb, cfg_override=body.get("params"))

    _run_job_async(job_name, _run)
    return JSONResponse({**r, "job_name": job_name, "queued": True})


@app.get("/api/jobs/{job_name}/preview")
def api_job_preview(job_name: str, time_sec: float = 5.0):
    job_dir = _safe_job_path(str(job_name))
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    vid = next((p for p in job_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv", ".mov"}), None)
    if not vid:
        return JSONResponse({"error": "无视频文件"}, status_code=404)
    thumb = generate_thumbnail(vid, job_dir / "preview.jpg", time_sec=time_sec)
    return FileResponse(str(thumb))


@app.get("/api/jobs/{job_name}/qc")
def api_job_qc(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    qc_path = job_dir / "qc_report.json"
    if qc_path.exists():
        return JSONResponse(json.loads(qc_path.read_text(encoding="utf-8")))
    summary = job_dir / "summary.json"
    if summary.exists():
        s = json.loads(summary.read_text(encoding="utf-8"))
        vid = s.get("final_video") or s.get("short_video")
        if vid and Path(vid).exists():
            return JSONResponse(analyze_video(Path(vid), load_config(), job_dir))
    return JSONResponse({"error": "无可质检视频"}, status_code=404)


@app.post("/api/jobs/restore")
async def api_restore_job(file: UploadFile = File(...)):
    import tempfile
    cfg = load_config()
    out_base = _output_base()
    out_base.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        restored = restore_job(tmp_path, out_base)
        return JSONResponse({"ok": True, "job": restored.name, "path": str(restored)})
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/api/batch/report")
def api_batch_report():
    cfg = load_config()
    watch = ROOT / (cfg.get("batch") or {}).get("watch_dir", "watch_in")
    return JSONResponse(build_batch_report(_output_base(), watch))


@app.get("/api/batch/report.html")
def api_batch_report_html():
    cfg = load_config()
    watch = ROOT / (cfg.get("batch") or {}).get("watch_dir", "watch_in")
    report = build_batch_report(_output_base(), watch)
    dest = ROOT / "logs" / "batch_report.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    export_batch_report_html(report, dest)
    return FileResponse(dest, media_type="text/html")


@app.get("/api/knowledge")
def api_knowledge_list():
    return JSONResponse(list_documents())


@app.post("/api/knowledge")
async def api_knowledge_save(request: Request):
    body = await request.json()
    name = body.get("name", "doc.md")
    content = body.get("content", "")
    p = save_document(name, content)
    return JSONResponse({"ok": True, "path": str(p)})


@app.get("/api/config/validate")
def api_config_validate():
    issues = validate_config(load_config())
    return JSONResponse({"ok": len(issues) == 0, "issues": issues})


@app.get("/api/vertical-templates")
def api_vertical_templates():
    return JSONResponse(list_vertical_templates())


@app.delete("/api/prompt-templates/{tid}")
def api_delete_prompt_template(tid: str):
    from src.prompt_templates import TEMPLATES_DIR
    path = TEMPLATES_DIR / f"{tid}.json"
    if path.exists():
        path.unlink()
        return JSONResponse({"ok": True})
    return JSONResponse({"error": "不存在"}, status_code=404)


@app.post("/api/jobs/{job_name}/backup")
def api_backup_job(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    z = backup_job(job_dir)
    return FileResponse(z, media_type="application/zip", filename=z.name)


@app.get("/api/plugins/user")
def api_user_plugins():
    return JSONResponse(discover_user_plugins())


@app.get("/api/dashboard")
def api_dashboard():
    return JSONResponse(build_dashboard(_output_base()))


@app.get("/api/template-market")
def api_template_market():
    return JSONResponse(list_market_templates())


@app.post("/api/template-market/{tid}/apply")
def api_apply_market_template(tid: str):
    cfg = apply_market_template(load_config(), tid)
    save_config(cfg)
    _reload_cfg()
    return JSONResponse({"ok": True, "template": tid})


@app.get("/api/jobs/compare")
def api_compare_jobs(job_a: str, job_b: str):
    da, db = _safe_job_path(job_a), _safe_job_path(job_b)
    if not da or not db:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return JSONResponse(compare_jobs(da, db))


@app.get("/api/ab-feedback")
def api_ab_feedback():
    return JSONResponse({"items": load_feedback(), "suggest": suggest_from_feedback()})


@app.post("/api/ab-feedback")
async def api_ab_feedback_save(request: Request):
    body = await request.json()
    row = record_feedback(body)
    return JSONResponse({"ok": True, "entry": row})


@app.post("/api/jobs/{job_name}/browser-publish/{platform}")
def api_browser_publish(job_name: str, platform: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return JSONResponse(run_browser_publish(job_dir, platform, load_config()))


@app.get("/api/jobs/{job_name}/preflight")
def api_job_preflight(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return JSONResponse(run_publish_preflight(job_dir, load_config()))


@app.post("/api/rag/reindex")
def api_rag_reindex():
    n = build_rag_index(load_config())
    return JSONResponse({"ok": True, "chunks": n})


@app.get("/api/team/tokens")
def api_team_tokens():
    return JSONResponse(load_team_tokens())


@app.post("/api/team/tokens")
async def api_team_create_token(request: Request):
    body = await request.json()
    entry = create_token(body.get("name", "user"), body.get("role", "editor"))
    return JSONResponse({"ok": True, "entry": entry})


@app.get("/api/offline/status")
def api_offline_status():
    cfg = load_config()
    return JSONResponse({"lm_studio": lm_studio_reachable(cfg), "offline_cfg": apply_offline_fallback(cfg).get("pipeline", {})})


@app.get("/api/jobs/db")
def api_jobs_db(status: str = "", limit: int = 100):
    return JSONResponse(list_indexed_jobs(status=status or None, limit=limit))


@app.get("/api/analytics/step-timing")
def api_step_timing_agg():
    return JSONResponse(step_timing_aggregate())


@app.post("/api/analytics/sync-stats")
def api_sync_stats(limit: int = 20):
    r = sync_all_jobs(_output_base(), load_config(), limit=limit)
    return JSONResponse(r)


@app.get("/api/jobs/{job_name}/variants")
def api_job_variants(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return JSONResponse({"variants": list_video_variants(job_dir)})


@app.get("/api/jobs/{job_name}/sprite")
def api_job_sprite(job_name: str, interval: int = 10):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    vid = next((p for p in job_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv", ".mov"}), None)
    if not vid:
        return JSONResponse({"error": "无视频"}, status_code=404)
    info = generate_thumbnails_sprite(vid, job_dir / "sprite")
    return JSONResponse(info)


@app.get("/api/jobs/{job_name}/compliance")
def api_job_compliance(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return JSONResponse(build_compliance_report(job_dir, load_config()))


@app.get("/api/batch/plan")
def api_batch_plan():
    nodes = load_batch_plan()
    return JSONResponse({"nodes": [{"video": n.video, "job_name": n.job_name, "priority": n.priority,
                                      "depends_on": n.depends_on, "status": n.status, "preset": n.preset} for n in nodes]})


@app.post("/api/batch/plan/from-watch")
def api_batch_plan_from_watch(preset: str = ""):
    cfg = load_config()
    watch = ROOT / (cfg.get("batch") or {}).get("watch_dir", "watch_in")
    nodes = batch_plan_from_watch(watch, preset=preset)
    save_batch_plan(nodes)
    return JSONResponse({"count": len(nodes)})


@app.post("/api/batch/plan/run-next")
def api_batch_run_next():
    nodes = load_batch_plan()
    n = next_runnable(nodes)
    if not n:
        return JSONResponse({"ok": False, "detail": "无可运行任务"})
    vp = Path(n.video)
    if not vp.exists():
        return JSONResponse({"ok": False, "detail": f"视频不存在: {n.video}"})
    job_name = n.job_name or f"{vp.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    n.job_name = job_name
    n.status = "running"
    save_batch_plan(nodes)
    job_dir = output_dir(load_config(), job_name)

    def _run(cb):
        run_pipeline(vp, job_dir=job_dir, preset=n.preset or None, on_step=cb)
        nodes2 = load_batch_plan()
        for node in nodes2:
            if node.job_name == job_name:
                node.status = "done"
        save_batch_plan(nodes2)

    _run_job_async(job_name, _run)
    return JSONResponse({"ok": True, "job_name": job_name})


@app.post("/api/jobs/{job_name}/series")
def api_job_series(job_name: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    vid = next((p for p in job_dir.iterdir() if p.suffix.lower() in {".mp4", ".mkv", ".mov"} and "_short_" not in p.stem), None)
    if not vid:
        return JSONResponse({"error": "无视频"}, status_code=404)
    transcript = (job_dir / "transcript.txt").read_text(encoding="utf-8") if (job_dir / "transcript.txt").exists() else ""
    seg_data = json.loads((job_dir / "segments.json").read_text(encoding="utf-8")) if (job_dir / "segments.json").exists() else {}
    segments = seg_data.get("segments", []) if isinstance(seg_data, dict) else []
    r = export_series_pack(job_dir, vid, transcript, segments, load_config())
    return JSONResponse(r)


@app.post("/api/jobs/{job_name}/segments/{index}/lock")
async def api_segment_lock(job_name: str, index: int, request: Request):
    body = await request.json()
    user = body.get("user", "anonymous")
    r = acquire_lock(job_name, index, user)
    return JSONResponse(r)


@app.delete("/api/jobs/{job_name}/segments/{index}/lock")
async def api_segment_unlock(job_name: str, index: int, request: Request):
    body = await request.json()
    release_lock(job_name, index, body.get("user", "anonymous"))
    return JSONResponse({"ok": True})


@app.get("/api/jobs/{job_name}/locks")
def api_segment_locks(job_name: str):
    return JSONResponse({"locks": list_locks(job_name)})


@app.get("/api/tenant")
def api_tenant_info():
    cfg = load_config()
    return JSONResponse({
        "enabled": bool((cfg.get("tenant") or {}).get("enabled")),
        "current": _current_tenant(),
        "base": str(_output_base()),
    })


@app.put("/api/jobs/{job_name}/chapters")
async def api_save_chapters(job_name: str, request: Request):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    body = await request.json()
    chapters = body.get("chapters") or []
    (job_dir / "chapters.json").write_text(json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"{c.get('time', '00:00')} {c.get('title', '')}" for c in chapters]
    (job_dir / "chapters_bilibili.txt").write_text("\n".join(lines), encoding="utf-8")
    (job_dir / "chapters_youtube.txt").write_text("\n".join(lines), encoding="utf-8")
    return JSONResponse({"ok": True})


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main() -> None:
    import uvicorn

    wcfg = _cfg.get("web") or {}
    configure_queue(int(wcfg.get("max_concurrent_jobs", 1)))
    scfg = _cfg.get("scheduler") or {}
    if scfg.get("enabled", True):
        interval = int(scfg.get("poll_interval_sec", 60))
        start_scheduler(_output_base(), interval)

    def _redis_handler(spec: dict[str, Any]) -> None:
        run_pipeline(
            Path(spec.get("video_path") or spec["job_dir"]),
            job_dir=Path(spec["job_dir"]) if spec.get("job_dir") else None,
            skip_cut=spec.get("skip_cut", False),
            skip_burn=spec.get("skip_burn", False),
            skip_copy=spec.get("skip_copy", False),
            skip_dub=spec.get("skip_dub", False),
            only_transcribe=spec.get("only_transcribe", False),
            preset=spec.get("preset"),
            cfg_override=spec.get("cfg_override"),
        )

    start_redis_worker(_redis_handler, _cfg)

    import multiprocessing
    multiprocessing.freeze_support()
    host = wcfg.get("host", "127.0.0.1")
    port = int(wcfg.get("port", 8766))
    uvicorn.run("web_app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
