#!/usr/bin/env python3
"""简易 Web 面板：查看任务、上传视频、触发处理。"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from src.config_loader import ROOT, load_config, output_dir
from src.pipeline import run_pipeline

app = FastAPI(title="video-promo-pipeline", version="2.0.0")
_cfg = load_config()
_jobs_lock = threading.Lock()
_running: dict[str, str] = {}


def _list_jobs() -> list[dict]:
    base = ROOT / _cfg.get("output", {}).get("dir", "output")
    if not base.exists():
        return []
    jobs: list[dict] = []
    for d in sorted(base.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        summary_path = d / "summary.json"
        item = {"name": d.name, "path": str(d), "mtime": d.stat().st_mtime}
        if summary_path.exists():
            try:
                item["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        with _jobs_lock:
            item["status"] = _running.get(d.name, "idle")
        jobs.append(item)
    return jobs


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>video-promo-pipeline</title>
<style>
body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem}
.card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}
button,input[type=file]{margin:.25rem 0}
code{background:#f4f4f4;padding:2px 6px;border-radius:4px}
</style></head><body>
<h1>video-promo-pipeline</h1>
<p>上传录屏 → 自动字幕 / 粗剪 / 文案。需本机已安装 FFmpeg、Python 依赖与 LM Studio。</p>
<form action="/upload" method="post" enctype="multipart/form-data" class="card">
  <label>选择视频 <input type="file" name="file" accept="video/*" required></label><br>
  <label><input type="checkbox" name="skip_copy" value="1"> 跳过文案</label><br>
  <button type="submit">开始处理</button>
</form>
<div class="card"><h2>任务列表</h2><div id="jobs">加载中…</div></div>
<script>
async function load(){const r=await fetch('/api/jobs');const j=await r.json();
document.getElementById('jobs').innerHTML=j.map(x=>`<div><b>${x.name}</b> [${x.status||'idle'}]
<br><code>${x.path}</code></div>`).join('')||'暂无任务';}
load();setInterval(load,5000);
</script></body></html>"""


@app.get("/api/jobs")
def api_jobs():
    return JSONResponse(_list_jobs())


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    skip_copy: str = Form(""),
):
    if not file.filename:
        return JSONResponse({"error": "无文件名"}, status_code=400)
    upload_dir = ROOT / "watch_in"
    upload_dir.mkdir(exist_ok=True)
    dest = upload_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)

    job_name = f"{dest.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    job_dir = output_dir(_cfg, job_name)

    def _run():
        with _jobs_lock:
            _running[job_name] = "running"
        try:
            run_pipeline(
                dest,
                config_path=None,
                job_dir=job_dir,
                skip_copy=bool(skip_copy),
            )
            with _jobs_lock:
                _running[job_name] = "done"
        except Exception as e:
            with _jobs_lock:
                _running[job_name] = f"error: {e}"

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"ok": True, "job": job_name, "job_dir": str(job_dir)})


def main() -> None:
    import uvicorn

    wcfg = _cfg.get("web") or {}
    host = wcfg.get("host", "127.0.0.1")
    port = int(wcfg.get("port", 8766))
    uvicorn.run("web_app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
