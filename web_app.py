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
from src.job_queue import acquire, configure as configure_queue, enqueue, release, status as queue_status
from src.lm_usage import estimate_cost, load_stats
from src.pipeline import run_pipeline
from src.presets import list_presets
from src.preflight import run_preflight
from src.progress_tracker import load_progress
from src.publish_pack import build_publish_pack, save_segments_and_srt
from src.service_checks import check_gpt_sovits, check_lm_studio_detail
from src.terminology import load_terminology, save_terminology, terminology_path

WEB_DIR = ROOT / "web"
STATIC_DIR = WEB_DIR / "static"
APP_VERSION = "3.5.0"
LATEST_VERSION_URL = "https://raw.githubusercontent.com/180024421/video-promo-pipeline/main/VERSION"

ASSETS_DIR = ROOT / "assets"

app = FastAPI(title="video-promo-pipeline", version=APP_VERSION)
_cfg = load_config()
_jobs_lock = threading.Lock()
_running: dict[str, dict[str, Any]] = {}
_ffmpeg_install: dict[str, Any] = {"status": "idle", "message": "", "progress": 0}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        cfg = load_config()
        token = (cfg.get("web") or {}).get("auth_token", "")
        path = request.url.path
        if token and path.startswith("/api/") and path not in ("/api/status", "/api/health", "/api/version"):
            hdr = request.headers.get("X-Auth-Token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
            q = request.query_params.get("token", "")
            if hdr != token and q != token:
                return JSONResponse({"error": "未授权，请设置 X-Auth-Token"}, status_code=401)
        if token and path.startswith("/ws/"):
            q = request.query_params.get("token", "")
            if q != token:
                return JSONResponse({"error": "未授权 WebSocket"}, status_code=401)
        return await call_next(request)


app.add_middleware(AuthMiddleware)


def _reload_cfg() -> dict[str, Any]:
    global _cfg
    _cfg = load_config()
    return _cfg


def _output_base() -> Path:
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
    return HTMLResponse(html)


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


@app.get("/api/jobs/{job_name}/files/{filename}")
def api_job_file(job_name: str, filename: str):
    job_dir = _safe_job_path(job_name)
    if not job_dir:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    fp = (job_dir / filename).resolve()
    if not str(fp).startswith(str(job_dir.resolve())) or not fp.is_file():
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    mime, _ = mimetypes.guess_type(str(fp))
    return FileResponse(fp, media_type=mime or "application/octet-stream", filename=fp.name)


@app.get("/api/presets")
def api_presets():
    return JSONResponse(list_presets())


def _run_job_async(job_name: str, fn) -> int:
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
            return

        with _jobs_lock:
            _running[job_name] = {"status": "running", "step": "初始化", "progress": 0}
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

            fn(on_step)
            with _jobs_lock:
                state = {"status": "done", "step": "完成", "progress": 100, "job": job_name}
                _running[job_name] = state
            broadcast_sync({"type": "job_progress", **state})
        except Exception as e:
            with _jobs_lock:
                state = {"status": "error", "error": str(e), "step": "失败", "progress": 0, "job": job_name}
                _running[job_name] = state
            broadcast_sync({"type": "job_progress", **state})
        finally:
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

    def _run(on_step):
        run_pipeline(
            dest,
            job_dir=job_dir,
            skip_cut=bool(skip_cut),
            skip_burn=bool(skip_burn),
            skip_copy=bool(skip_copy),
            skip_dub=bool(skip_dub),
            only_transcribe=bool(only_transcribe),
            preset=preset or None,
            cfg_override=cfg_override or None,
            on_step=on_step,
        )

    pos = _run_job_async(job_name, _run)
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


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main() -> None:
    import uvicorn

    wcfg = _cfg.get("web") or {}
    configure_queue(int(wcfg.get("max_concurrent_jobs", 1)))
    host = wcfg.get("host", "127.0.0.1")
    port = int(wcfg.get("port", 8766))
    uvicorn.run("web_app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
