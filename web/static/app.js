const $ = (s, p = document) => p.querySelector(s);
const $$ = (s, p = document) => [...p.querySelectorAll(s)];

const _nativeFetch = window.fetch.bind(window);
window.fetch = (url, opts = {}) => {
  const token = localStorage.getItem('auth_token') || '';
  if (token) {
    opts.headers = { ...(opts.headers || {}), 'X-Auth-Token': token };
  }
  return _nativeFetch(url, opts);
};

let currentJob = null;
let configData = {};

// ── Navigation ──
$$('.nav-item').forEach(el => {
  el.addEventListener('click', () => {
    $$('.nav-item').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    const page = el.dataset.page;
    $$('.page').forEach(p => p.classList.remove('active'));
    $(`#page-${page}`).classList.add('active');
    if (page === 'dashboard') loadStatus();
    if (page === 'jobs') loadJobs();
    if (page === 'batch') loadBatch();
    if (page === 'config') loadConfig();
    if (page === 'copy') loadCopyConfig();
    if (page === 'terminology') loadTerminology();
    if (page === 'assets') loadAssets();
  });
});

function toast(msg, ok = true) {
  const t = document.createElement('div');
  t.className = `toast ${ok ? 'toast-ok' : 'toast-err'}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

let wsConnected = false;

function connectWebSocket() {
  const token = localStorage.getItem('auth_token') || '';
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${location.host}/ws/progress${token ? '?token=' + encodeURIComponent(token) : ''}`;
  try {
    const ws = new WebSocket(url);
    ws.onopen = () => { wsConnected = true; };
    ws.onclose = () => { wsConnected = false; setTimeout(connectWebSocket, 5000); };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'job_progress' && msg.job) {
          if ($('#page-jobs').classList.contains('active')) loadJobs();
          if (currentJob === msg.job && $('#detail-overlay').classList.contains('open')) {
            $('#detail-status').innerHTML = `<span class="badge ${msg.status==='done'?'badge-ok':msg.status==='running'?'badge-run':msg.status==='error'?'badge-err':'badge-warn'}">${msg.status}${msg.step?' · '+msg.step:''}</span>`;
          }
        }
      } catch (_) {}
    };
    setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 25000);
  } catch (_) {}
}

async function loadBatch() {
  const r = await fetch('/api/batch/watch');
  const d = await r.json();
  const el = $('#batch-list');
  if (!d.pending?.length) {
    el.innerHTML = '<div class="empty">watch_in 暂无待处理视频</div>';
    return;
  }
  el.innerHTML = `<p>待处理 ${d.count} 个 · 目录: ${escHtml(d.watch_dir)}</p>` +
    d.pending.map(f => `<div class="file-tag">${escHtml(f.name)} (${(f.size/1024/1024).toFixed(1)} MB)</div>`).join('');
}

$('#batch-refresh-btn')?.addEventListener('click', loadBatch);
$('#batch-process-btn')?.addEventListener('click', async () => {
  const r = await fetch('/api/batch/process', { method: 'POST' });
  const d = await r.json();
  toast(d.ok ? `已启动: ${(d.started||[]).join(', ')}` : (d.error || '失败'), d.ok);
  loadBatch();
  loadJobs();
});

async function checkVersion() {
  try {
    const r = await fetch('/api/version');
    const d = await r.json();
    if ($('#app-version')) $('#app-version').textContent = `v${d.version}`;
    const banner = $('#version-banner');
    if (d.update_available && banner) {
      banner.style.display = 'block';
      $('#version-banner-text').textContent = `当前 v${d.version}，最新 v${d.latest}`;
    }
  } catch (_) {}
}

// ── Dashboard ──
let _ffmpegPollTimer = null;

async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const grid = $('#status-grid');
    const items = [
      ['FFmpeg', d.checks.ffmpeg],
      ['faster-whisper', d.checks.whisper],
      ['auto-editor', d.checks.auto_editor],
      ['LM Studio', d.checks.lm_studio],
      ['edge-tts', d.checks.edge_tts],
    ];
    const gs = d.checks.gpt_sovits;
    if (gs && !gs.skipped) {
      items.push(['GPT-SoVITS', gs.ok]);
    }
    if (d.checks.queue) {
      items.push(['GPU 队列', d.checks.queue.active_count < d.checks.queue.max_concurrent]);
      if (d.checks.queue.pending_count > 0) {
        grid.innerHTML += `<div class="status-item" style="grid-column:1/-1"><div class="label">排队任务</div><div style="font-size:0.8rem">${d.checks.queue.pending.join(', ') || d.checks.queue.pending_count + ' 个'}</div></div>`;
      }
    }
    grid.innerHTML = items.map(([label, ok]) => `
      <div class="status-item">
        <div class="label">${label}</div>
        <span class="badge ${ok ? 'badge-ok' : 'badge-err'}">${ok ? '正常' : '未就绪'}</span>
      </div>
    `).join('');
    if (d.checks.ffmpeg_path) {
      grid.innerHTML += `<div class="status-item" style="grid-column:1/-1">
        <div class="label">FFmpeg 路径</div>
        <div style="font-size:0.75rem;margin-top:4px;word-break:break-all;color:var(--text-muted)">${d.checks.ffmpeg_path}</div>
      </div>`;
    }
    $('#lmstudio-hint-card').style.display = d.checks.lm_studio ? 'none' : 'block';
    window._lmConnected = !!d.checks.lm_studio;
    if ($('#upload-lm-warn')) updateUploadLmWarn();
    if (d.checks.lm_models?.length) {
      grid.innerHTML += `<div class="status-item" style="grid-column:1/-1">
        <div class="label">LM Studio 模型</div>
        <div style="font-size:0.8rem;margin-top:4px">${d.checks.lm_models.join(', ')}</div>
      </div>`;
    }
    $('#jobs-count').textContent = d.jobs_count;
    if (d.version && $('#app-version')) $('#app-version').textContent = `v${d.version}`;
    if (d.lm_usage) {
      grid.innerHTML += `<div class="status-item" style="grid-column:1/-1"><div class="label">LM 调用</div>
        <div style="font-size:0.8rem">${d.lm_usage.total_calls} 次 · ${d.lm_usage.total_prompt_tokens + d.lm_usage.total_completion_tokens} tokens</div></div>`;
    }

    const card = $('#ffmpeg-install-card');
    const fi = d.checks.ffmpeg_install || {};
    if (!d.checks.ffmpeg) {
      card.style.display = 'block';
      if (fi.status === 'running') {
        showFfmpegProgress(fi.message, fi.progress);
        startFfmpegPoll();
      } else if (fi.status === 'error') {
        showFfmpegProgress(fi.message || '安装失败', 0);
        $('#btn-ffmpeg-install').disabled = false;
      }
    } else {
      card.style.display = 'none';
      stopFfmpegPoll();
    }
  } catch (e) {
    toast('状态加载失败', false);
  }
}

function showFfmpegProgress(msg, pct) {
  $('#ffmpeg-install-progress').style.display = 'block';
  $('#ffmpeg-install-msg').textContent = msg || '处理中…';
  $('#ffmpeg-install-bar').style.width = `${pct || 0}%`;
}

function startFfmpegPoll() {
  stopFfmpegPoll();
  _ffmpegPollTimer = setInterval(async () => {
    const r = await fetch('/api/ffmpeg/install-status');
    const fi = await r.json();
    showFfmpegProgress(fi.message, fi.progress);
    if (fi.status === 'done') {
      toast('FFmpeg 安装完成');
      stopFfmpegPoll();
      loadStatus();
    } else if (fi.status === 'error') {
      toast(fi.message || '安装失败', false);
      stopFfmpegPoll();
      $('#btn-ffmpeg-install').disabled = false;
    }
  }, 1500);
}

function stopFfmpegPoll() {
  if (_ffmpegPollTimer) {
    clearInterval(_ffmpegPollTimer);
    _ffmpegPollTimer = null;
  }
}

$('#btn-ffmpeg-install')?.addEventListener('click', async () => {
  const btn = $('#btn-ffmpeg-install');
  btn.disabled = true;
  showFfmpegProgress('开始下载…', 0);
  try {
    const r = await fetch('/api/ffmpeg/install', { method: 'POST' });
    const d = await r.json();
    if (d.ok) {
      startFfmpegPoll();
    } else {
      toast(d.error || '无法开始安装', false);
      btn.disabled = false;
    }
  } catch (e) {
    toast('请求失败: ' + e.message, false);
    btn.disabled = false;
  }
});

// ── Upload ──
const dropZone = $('#drop-zone');
const fileInput = $('#file-input');

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) {
    fileInput.files = e.dataTransfer.files;
    $('#file-name').textContent = e.dataTransfer.files[0].name;
  }
});
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) $('#file-name').textContent = fileInput.files[0].name;
});

function updateUploadLmWarn() {
  const el = $('#upload-lm-warn');
  if (!el) return;
  const onlyTx = $('#only-transcribe')?.checked;
  const skipCopy = $('#skip-copy')?.checked;
  el.style.display = (!window._lmConnected && !onlyTx && !skipCopy) ? 'block' : 'none';
}
['only-transcribe', 'skip-copy'].forEach(id => {
  $(`#${id}`)?.addEventListener('change', updateUploadLmWarn);
});

$('#upload-form').addEventListener('submit', async e => {
  e.preventDefault();
  if (!fileInput.files.length) return toast('请选择视频', false);
  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  if ($('#skip-cut').checked) fd.append('skip_cut', '1');
  if ($('#skip-burn').checked) fd.append('skip_burn', '1');
  if ($('#skip-copy').checked) fd.append('skip_copy', '1');
  if ($('#skip-dub').checked) fd.append('skip_dub', '1');
  if ($('#only-transcribe').checked) fd.append('only_transcribe', '1');
  if ($('#only-transcribe').checked || $('#skip-copy').checked) fd.append('force_start', '1');
  const persona = $('#upload-persona').value.trim();
  const topic = $('#upload-topic').value.trim();
  const keywords = $('#upload-keywords').value.trim();
  const platforms = $('#upload-platforms').value;
  if (persona) fd.append('persona', persona);
  if (topic) fd.append('topic', topic);
  if (keywords) fd.append('keywords', keywords);
  if (platforms) fd.append('platforms', platforms);
  const preset = $('#upload-preset').value;
  if (preset) fd.append('preset', preset);
  $('#upload-btn').disabled = true;
  $('#upload-btn').textContent = '处理中...';
  try {
    const r = await fetch('/api/upload', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.ok) {
      toast(d.warnings?.length ? `任务已创建（${d.warnings[0]}）` : `任务已创建: ${d.job}`);
      fileInput.value = '';
      $('#file-name').textContent = '';
      $$('.nav-item').forEach(n => n.classList.remove('active'));
      $('[data-page=jobs]').classList.add('active');
      $$('.page').forEach(p => p.classList.remove('active'));
      $('#page-jobs').classList.add('active');
      loadJobs();
    } else {
      toast(d.error || '上传失败', false);
    }
  } catch (err) {
    toast('上传失败: ' + err.message, false);
  }
  $('#upload-btn').disabled = false;
  $('#upload-btn').textContent = '开始处理';
});

// ── Jobs ──
async function loadJobs() {
  try {
    const r = await fetch('/api/jobs');
    const jobs = await r.json();
    const el = $('#job-list');
    if (!jobs.length) {
      el.innerHTML = '<div class="empty">暂无任务，去上传页面添加视频吧</div>';
      return;
    }
    el.innerHTML = jobs.map(j => {
      const st = j.status || 'idle';
      const badge = st === 'done' ? 'badge-ok' : st === 'running' ? 'badge-run' : st === 'error' ? 'badge-err' : 'badge-warn';
      const stText = st === 'done' ? '完成' : st === 'running' ? (j.step || '处理中') : st === 'queued' ? (j.step || '排队中') : st === 'error' ? '失败' : '空闲';
      const prog = j.progress || 0;
      const progBar = (st === 'running' || st === 'queued') ? `<div style="height:4px;background:#333;border-radius:2px;margin-top:6px"><div style="width:${prog}%;height:100%;background:var(--accent);border-radius:2px"></div></div>` : '';
      const files = (j.files || []).map(f => `<span class="file-tag">${f.name}</span>`).join('');
      return `<div class="job-card" data-job="${j.name}">
        <div class="job-card-header">
          <h3>${j.name}</h3>
          <span class="badge ${badge}">${stText}</span>
        </div>
        <div class="job-card-meta">${j.created || ''} · ${(j.files||[]).length} 个文件</div>
        ${progBar}
        <div class="job-card-files">${files}</div>
      </div>`;
    }).join('');
    $$('.job-card').forEach(card => {
      card.addEventListener('click', () => openJobDetail(card.dataset.job));
    });
  } catch (e) {
    toast('任务列表加载失败', false);
  }
}

function renderStepTimeline(prog) {
  if (!prog || !prog.steps) return '<div class="empty">暂无步骤记录</div>';
  const { steps, current, completed = [], skipped = [] } = prog;
  const allDone = current === '完成';
  return `<div class="step-timeline">${steps.map(name => {
    let cls = '';
    if (skipped.includes(name)) cls = 'skipped';
    else if (allDone || completed.includes(name)) cls = 'done';
    else if (current === name) cls = 'running';
    const icon = cls === 'done' ? '✓' : cls === 'running' ? '▶' : '·';
    return `<div class="step-item ${cls}"><div class="step-dot">${icon}</div><div class="step-label">${name}</div></div>`;
  }).join('')}</div>`;
}

function renderNarrationEditor(tl, name) {
  const segs = tl.segments || [];
  const rows = segs.map((s) => `
    <tr><td><input type="number" step="0.1" class="seg-start" value="${Number(s.start).toFixed(1)}"></td>
    <td><input type="number" step="0.1" class="seg-end" value="${Number(s.end).toFixed(1)}"></td>
    <td><input type="text" class="seg-text" value="${escAttr(s.text || '')}"></td></tr>`).join('');
  return `<p class="hint-text">编辑解说稿后保存，再点「重跑配音」。</p>
    <table class="seg-table"><thead><tr><th>开始</th><th>结束</th><th>文本</th></tr></thead><tbody>${rows}</tbody></table>
    <button class="btn btn-sm btn-primary" id="save-narration-btn" style="margin-top:8px">保存解说稿</button>`;
}

function renderSegmentEditor(segments, name) {
  const maxT = Math.max(...segments.map(s => s.end), 60);
  const rows = segments.map((s, i) => `
    <tr data-idx="${i}">
      <td><input type="range" min="0" max="${maxT.toFixed(0)}" step="0.1" class="tx-start-range" value="${Number(s.start).toFixed(2)}" style="width:80px">
          <input type="number" step="0.1" class="tx-start" value="${Number(s.start).toFixed(2)}" style="width:60px"></td>
      <td><input type="range" min="0" max="${maxT.toFixed(0)}" step="0.1" class="tx-end-range" value="${Number(s.end).toFixed(2)}" style="width:80px">
          <input type="number" step="0.1" class="tx-end" value="${Number(s.end).toFixed(2)}" style="width:60px"></td>
      <td><input type="text" class="tx-text" value="${escAttr(s.text || '')}"></td>
      <td><span class="tx-speaker">${escHtml(s.speaker || '')}</span></td>
    </tr>`).join('');
  return `<p class="hint-text">拖动滑块或编辑数字校对字幕；保存后点「重跑字幕」。</p>
    <table class="seg-table"><thead><tr><th>开始</th><th>结束</th><th>文本</th><th>说话人</th></tr></thead><tbody>${rows}</tbody></table>
    <button class="btn btn-sm btn-primary" id="save-segments-btn" style="margin-top:8px">保存字幕</button>`;
}

function bindSegmentSliders(container) {
  container.querySelectorAll('tr').forEach(tr => {
    const sr = tr.querySelector('.tx-start-range');
    const sn = tr.querySelector('.tx-start');
    const er = tr.querySelector('.tx-end-range');
    const en = tr.querySelector('.tx-end');
    if (sr && sn) { sr.oninput = () => { sn.value = sr.value; }; sn.oninput = () => { sr.value = sn.value; }; }
    if (er && en) { er.oninput = () => { en.value = er.value; }; en.oninput = () => { en.value = er.value; }; }
  });
}

async function saveNarrationFromTable(tl, name) {
  const segs = [];
  $$('#tab-timeline tbody tr').forEach(tr => {
    segs.push({
      start: parseFloat(tr.querySelector('.seg-start').value) || 0,
      end: parseFloat(tr.querySelector('.seg-end').value) || 0,
      text: tr.querySelector('.seg-text').value,
    });
  });
  const payload = { ...tl, segments: segs };
  await fetch(`/api/jobs/${encodeURIComponent(name)}/narration`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  toast('解说稿已保存，可点「重跑配音」生效');
}

// ── Job Detail ──
async function openJobDetail(name) {
  currentJob = name;
  const r = await fetch(`/api/jobs/${encodeURIComponent(name)}`);
  const d = await r.json();
  if (d.error) return toast(d.error, false);

  $('#detail-title').textContent = name;
  const st = d.status || 'idle';
  $('#detail-status').innerHTML = `<span class="badge ${st==='done'?'badge-ok':st==='running'?'badge-run':st==='error'?'badge-err':'badge-warn'}">${st}${d.step?' · '+d.step:''}</span>`;
  if (d.error) $('#detail-status').innerHTML += `<span style="color:var(--error);margin-left:8px;font-size:0.8rem">${d.error}</span>`;

  // Files tab
  const filesEl = $('#tab-files');
  filesEl.innerHTML = (d.files || []).map(f => {
    const url = `/api/jobs/${encodeURIComponent(name)}/files/${encodeURIComponent(f.name)}`;
    if (f.type === 'video') return `<div style="margin-bottom:1rem"><strong>${f.name}</strong><video controls src="${url}"></video></div>`;
    if (f.type === 'image') return `<div style="margin-bottom:1rem"><strong>${f.name}</strong><br><img class="preview-img" src="${url}"></div>`;
    if (f.type === 'text' || f.type === 'json' || f.type === 'subtitle') {
      const key = f.name.replace(/\./g, '_');
      const content = d[key] || d[f.name.replace('.','_')] || '';
      return `<div class="copy-block"><h4>${f.name}</h4><div class="preview-box">${escHtml(content)}</div>
        <button class="btn btn-sm btn-secondary" onclick="copyText(this)" data-text="${escAttr(content)}">复制</button></div>`;
    }
    return `<div class="file-tag" style="display:inline-block;margin:4px"><a href="${url}" target="_blank" style="color:var(--accent)">${f.name}</a> (${(f.size/1024).toFixed(1)}KB)</div>`;
  }).join('') || '<div class="empty">暂无文件</div>';

  const shortVids = (d.files || []).filter(f => f.name.includes('_short_') && f.type === 'video');
  if (shortVids.length > 1) {
    filesEl.innerHTML += '<div class="card" style="margin-top:1rem"><h4>竖屏多段对比</h4><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px">' +
      shortVids.map(f => {
        const url = `/api/jobs/${encodeURIComponent(name)}/files/${encodeURIComponent(f.name)}`;
        return `<div><strong>${f.name}</strong><video controls src="${url}" style="width:100%"></video></div>`;
      }).join('') + '</div></div>';
  }

  fetch(`/api/jobs/${encodeURIComponent(name)}/upload-progress`).then(r => r.json()).then(up => {
    if (up && up.status === 'uploading') {
      filesEl.innerHTML += `<div class="hint-text" style="margin-top:8px">B站上传: ${up.percent || 0}% — ${up.message || ''}</div>`;
    }
  }).catch(() => {});

  // Copy tab
  const copyEl = $('#tab-copy');
  const promo = d.promo_copy || {};
  let copyHtml = '';
  if (promo.bilibili) {
    const b = promo.bilibili;
    copyHtml += `<div class="copy-block"><h4>B站标题候选</h4><div class="preview-box">${(b.titles||[]).map((t,i)=>`${i+1}. ${t}`).join('\n')}</div></div>`;
    copyHtml += `<div class="copy-block"><h4>B站简介</h4><div class="preview-box">${escHtml(b.description||'')}</div>
      <button class="btn btn-sm btn-secondary" onclick="copyText(this)" data-text="${escAttr(b.description||'')}">复制简介</button></div>`;
    if (b.tags) copyHtml += `<div class="copy-block"><h4>标签</h4><div class="preview-box">${b.tags.join(', ')}</div></div>`;
  }
  if (promo.xiaohongshu) {
    const x = promo.xiaohongshu;
    copyHtml += `<div class="copy-block"><h4>小红书标题</h4><div class="preview-box">${escHtml(x.title||'')}</div></div>`;
    copyHtml += `<div class="copy-block"><h4>小红书正文</h4><div class="preview-box">${escHtml(x.body||'')}</div>
      <button class="btn btn-sm btn-secondary" onclick="copyText(this)" data-text="${escAttr((x.title||'')+'\n\n'+(x.body||'')+'\n\n'+(x.topics||[]).join(' '))}">复制全文</button></div>`;
  }
  if (promo.short_hooks) {
    copyHtml += `<div class="copy-block"><h4>前三秒钩子</h4><div class="preview-box">${promo.short_hooks.map((h,i)=>`${i+1}. ${h}`).join('\n')}</div></div>`;
  }
  if (d.promo_copy_md) {
    copyHtml += `<div class="copy-block"><h4>完整 Markdown</h4><div class="preview-box">${escHtml(d.promo_copy_md)}</div></div>`;
  }
  copyEl.innerHTML = copyHtml || '<div class="empty">暂无文案，点击下方重新生成</div>';

  // Transcript tab
  $('#tab-transcript').innerHTML = d.transcript_txt
    ? `<div class="preview-box">${escHtml(d.transcript_txt)}</div>`
    : '<div class="empty">暂无转写文本</div>';

  const tl = d.narration;
  const tlEl = $('#tab-timeline');
  if (tl && tl.segments) {
    tlEl.innerHTML = renderNarrationEditor(tl, name);
    $('#save-narration-btn')?.addEventListener('click', () => saveNarrationFromTable(tl, name));
  } else {
    tlEl.innerHTML = '<div class="empty">暂无 narration.json（需开启 AI 配音）</div>';
  }

  $('#tab-steps').innerHTML = renderStepTimeline(d.pipeline_progress);

  const segData = d.segments;
  const segEl = $('#tab-segments');
  if (segData?.segments?.length) {
    segEl.innerHTML = renderSegmentEditor(segData.segments, name);
    bindSegmentSliders($('#tab-segments'));
    $('#save-segments-btn')?.addEventListener('click', async () => {
      const segs = [];
      $$('#tab-segments tbody tr').forEach(tr => {
        segs.push({
          start: parseFloat(tr.querySelector('.tx-start').value) || 0,
          end: parseFloat(tr.querySelector('.tx-end').value) || 0,
          text: tr.querySelector('.tx-text').value,
        });
      });
      await fetch(`/api/jobs/${encodeURIComponent(name)}/segments`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ segments: segs }),
      });
      toast('字幕已保存，可点「重跑字幕」');
    });
  } else {
    segEl.innerHTML = '<div class="empty">暂无 segments.json</div>';
  }

  $('#tab-logs').innerHTML = '<div class="preview-box" id="logs-box">加载日志...</div>';
  fetch(`/api/jobs/${encodeURIComponent(name)}/logs`).then(r => r.json()).then(l => {
    $('#logs-box').textContent = l.logs || '暂无日志';
  });

  $('#tab-publish').innerHTML = '<div class="empty">加载发布包...</div>';
  $('#tab-publish').innerHTML = '<div class="empty">加载发布包...</div>';
  fetch(`/api/jobs/${encodeURIComponent(name)}/publish-pack`).then(r => r.json()).then(p => {
    let html = '<div class="copy-block"><h4>一键复制</h4>';
    for (const [k, v] of Object.entries(p.clipboard || {})) {
      html += `<div style="margin:8px 0"><strong>${k}</strong><div class="preview-box">${escHtml(String(v))}</div>
        <button class="btn btn-sm btn-secondary" onclick="copyText(this)" data-text="${escAttr(String(v))}">复制</button></div>`;
    }
    if (p.short_clips?.length) html += `<p class="hint-text">竖屏片段: ${p.short_clips.join(', ')}</p>`;
    html += '</div>';
    $('#tab-publish').innerHTML = html || '<div class="empty">暂无</div>';
  });

  $('#tab-vision').innerHTML = '<div class="empty">加载中...</div>';
  fetch(`/api/jobs/${encodeURIComponent(name)}/vision-plan`).then(r => r.json()).then(v => {
    if (!v.pending?.clips?.length) {
      $('#tab-vision').innerHTML = '<div class="empty">无视觉剪辑方案</div>';
      return;
    }
    const clips = v.pending.clips.map(c => `${c.start}s-${c.end}s: ${c.reason || ''}`).join('\n');
    $('#tab-vision').innerHTML = `<div class="preview-box">${escHtml(clips)}</div>
      <p class="hint-text">${v.confirmed ? '已批准' : '待批准 — 确认后请重跑智能剪辑'}</p>
      ${v.confirmed ? '' : '<button class="btn btn-sm btn-primary" id="approve-vision-btn">批准视觉方案</button>'}`;
    $('#approve-vision-btn')?.addEventListener('click', async () => {
      await fetch(`/api/jobs/${encodeURIComponent(name)}/vision-approve`, { method: 'POST' });
      toast('已批准，请重跑智能剪辑相关步骤');
      openJobDetail(name);
    });
  });

  $('#dub-ab-btn').onclick = async () => {
    const r = await fetch(`/api/jobs/${encodeURIComponent(name)}/dub-ab`, { method: 'POST' });
    const j = await r.json();
    toast(j.ok ? '正在生成 AB 双音色' : (j.error || '失败'), j.ok);
  };

  $('#delete-job-btn').onclick = async () => {
    if (!confirm('确定删除此任务及全部文件？')) return;
    const r = await fetch(`/api/jobs/${encodeURIComponent(name)}`, { method: 'DELETE' });
    const j = await r.json();
    if (j.ok) { toast('已删除'); $('#detail-overlay').classList.remove('open'); loadJobs(); }
    else toast(j.error || '删除失败', false);
  };

  $('#download-zip-btn').style.display = 'inline-block';
  $('#download-zip-btn').href = `/api/jobs/${encodeURIComponent(name)}/download.zip`;

  $$('.rerun-btn').forEach(btn => {
    btn.onclick = async () => {
      const r = await fetch(`/api/jobs/${encodeURIComponent(name)}/rerun/${btn.dataset.step}`, {method:'POST'});
      const j = await r.json();
      toast(j.ok ? `正在重跑: ${btn.dataset.step}` : (j.error||'失败'), j.ok);
      setTimeout(() => openJobDetail(name), 2000);
    };
  });

  $$('.tab-btn').forEach(t => t.classList.remove('active'));
  $$('.tab-content').forEach(t => t.classList.remove('active'));
  $('[data-tab=files]').classList.add('active');
  $('#tab-files').classList.add('active');
  $('#detail-overlay').classList.add('open');
}

$('#detail-close').addEventListener('click', () => $('#detail-overlay').classList.remove('open'));
$('#detail-overlay').addEventListener('click', e => { if (e.target === $('#detail-overlay')) $('#detail-overlay').classList.remove('open'); });

$$('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('.tab-btn').forEach(t => t.classList.remove('active'));
    $$('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    $(`#tab-${btn.dataset.tab}`).classList.add('active');
  });
});

$('#regen-copy-btn').addEventListener('click', async () => {
  if (!currentJob) return;
  const r = await fetch(`/api/jobs/${encodeURIComponent(currentJob)}/regenerate-copy`, { method: 'POST' });
  const d = await r.json();
  if (d.ok) { toast('文案重新生成中...'); setTimeout(() => openJobDetail(currentJob), 3000); }
  else toast(d.error || '失败', false);
});

function copyText(btn) {
  navigator.clipboard.writeText(btn.dataset.text).then(() => toast('已复制'));
}

function escHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return s.replace(/"/g, '&quot;').replace(/\n/g, '&#10;'); }

function toggleDubEngineFields() {
  const engine = $('#cfg-dub-engine')?.value || 'edge-tts';
  if ($('#cfg-dub-voice-row')) $('#cfg-dub-voice-row').style.display = engine === 'edge-tts' ? 'block' : 'none';
  const showClone = engine === 'gpt-sovits';
  ['cfg-gptsovits-row', 'cfg-voice-clone-row', 'cfg-voice-clone-prompt-row'].forEach(id => {
    const el = $(`#${id}`);
    if (el) el.style.display = showClone ? 'block' : 'none';
  });
}

// ── Config (LM Studio + Whisper) ──
async function loadConfig() {
  const r = await fetch('/api/config');
  configData = await r.json();
  const lm = configData.lm_studio || {};
  const wh = configData.whisper || {};
  const wf = configData.workflow || {};
  const pipe = configData.pipeline || {};
  const clip = configData.clip_short || {};
  const bgm = clip.bgm || {};
  $('#cfg-lm-url').value = lm.base_url || '';
  $('#cfg-lm-model').value = lm.model || '';
  $('#cfg-lm-temp').value = lm.temperature ?? 0.7;
  $('#cfg-lm-tokens').value = lm.max_tokens ?? 4096;
  $('#cfg-lm-timeout').value = lm.timeout ?? 120;
  $('#cfg-lm-retries').value = lm.max_retries ?? 3;
  $('#cfg-lm-enabled').checked = lm.enabled !== false;
  $('#cfg-whisper-model').value = wh.model || 'small';
  $('#cfg-whisper-device').value = wh.device || 'cuda';
  $('#cfg-whisper-lang').value = wh.language || 'zh';
  if ($('#cfg-whisper-chunk-min')) $('#cfg-whisper-chunk-min').value = wh.chunk_minutes ?? 15;
  if ($('#cfg-whisper-chunk-threshold')) $('#cfg-whisper-chunk-threshold').value = wh.chunk_if_longer_sec ?? 1800;
  if ($('#cfg-whisper-clear-gpu')) $('#cfg-whisper-clear-gpu').checked = wh.clear_gpu_cache !== false;
  if ($('#cfg-quality-preset')) $('#cfg-quality-preset').value = (configData.video_quality || {}).preset || 'balanced';
  if ($('#cfg-workflow-preset')) $('#cfg-workflow-preset').value = wf.preset || '';
  if ($('#cfg-subtitle-mode')) $('#cfg-subtitle-mode').value = pipe.subtitle_mode || 'burn';
  const nar = configData.narration || {};
  const dub = configData.dubbing || {};
  const smart = configData.smart_cut || {};
  const gsv = dub.gpt_sovits || {};
  const vc = dub.voice_clone || {};
  $('#cfg-narration-enabled').checked = nar.enabled === true;
  $('#cfg-narration-mode').value = nar.mode || 'commentary';
  if ($('#cfg-dub-engine')) $('#cfg-dub-engine').value = dub.engine || 'edge-tts';
  $('#cfg-dub-voice').value = dub.voice || 'zh-CN-YunxiNeural';
  $('#cfg-dub-audio-mode').value = dub.audio_mode || 'replace';
  if ($('#cfg-gptsovits-url')) $('#cfg-gptsovits-url').value = gsv.base_url || 'http://127.0.0.1:9880';
  if ($('#cfg-voice-clone-audio')) $('#cfg-voice-clone-audio').value = vc.reference_audio || gsv.reference_audio || '';
  if ($('#cfg-voice-clone-prompt')) $('#cfg-voice-clone-prompt').value = vc.prompt_text || gsv.prompt_text || '';
  $('#cfg-smart-cut-enabled').checked = smart.enabled === true;
  if ($('#cfg-smart-cut-duration')) $('#cfg-smart-cut-duration').value = smart.target_duration_sec ?? 90;
  if ($('#cfg-vision-enabled')) $('#cfg-vision-enabled').checked = (configData.vision || {}).enabled === true;
  if ($('#cfg-broll-enabled')) $('#cfg-broll-enabled').checked = (configData.broll || {}).enabled === true;
  if ($('#cfg-i18n-enabled')) $('#cfg-i18n-enabled').checked = (configData.i18n || {}).enabled === true;
  if ($('#cfg-short-enabled')) $('#cfg-short-enabled').checked = clip.enabled !== false;
  if ($('#cfg-short-duration')) $('#cfg-short-duration').value = clip.duration_sec ?? 75;
  if ($('#cfg-bgm-enabled')) $('#cfg-bgm-enabled').checked = bgm.enabled === true;
  if ($('#cfg-bgm-file')) $('#cfg-bgm-file').value = bgm.file || '';
  if ($('#cfg-bgm-ducking')) $('#cfg-bgm-ducking').checked = bgm.ducking !== false;
  if ($('#cfg-multi-clip')) $('#cfg-multi-clip').value = clip.multi_clip_count ?? 1;
  const az = (configData.dubbing || {}).azure || {};
  if ($('#cfg-azure-key')) $('#cfg-azure-key').value = az.key || '';
  if ($('#cfg-azure-region')) $('#cfg-azure-region').value = az.region || 'eastasia';
  toggleDubEngineFields();
}

$('#cfg-dub-engine')?.addEventListener('change', toggleDubEngineFields);

$('#save-lm-config').addEventListener('click', async () => {
  configData.lm_studio = {
    ...configData.lm_studio,
    enabled: $('#cfg-lm-enabled').checked,
    base_url: $('#cfg-lm-url').value,
    model: $('#cfg-lm-model').value,
    temperature: parseFloat($('#cfg-lm-temp').value),
    max_tokens: parseInt($('#cfg-lm-tokens').value),
    timeout: parseInt($('#cfg-lm-timeout').value),
    max_retries: parseInt($('#cfg-lm-retries').value),
    api_key: 'lm-studio',
    json_retry: true,
  };
  configData.whisper = {
    ...configData.whisper,
    model: $('#cfg-whisper-model').value,
    device: $('#cfg-whisper-device').value,
    language: $('#cfg-whisper-lang').value,
    compute_type: 'float16',
    chunk_minutes: parseFloat($('#cfg-whisper-chunk-min').value),
    chunk_if_longer_sec: parseFloat($('#cfg-whisper-chunk-threshold').value),
    clear_gpu_cache: $('#cfg-whisper-clear-gpu')?.checked !== false,
  };
  configData.video_quality = {
    ...(configData.video_quality || {}),
    preset: $('#cfg-quality-preset')?.value || 'balanced',
  };
  configData.workflow = {
    ...configData.workflow,
    preset: $('#cfg-workflow-preset').value,
  };
  configData.pipeline = {
    ...configData.pipeline,
    subtitle_mode: $('#cfg-subtitle-mode').value,
  };
  configData.narration = {
    ...configData.narration,
    enabled: $('#cfg-narration-enabled').checked,
    mode: $('#cfg-narration-mode').value,
    use_lm: true,
    style: (configData.narration || {}).style || '专业解说，口语化，节奏紧凑',
    persona: (configData.narration || {}).persona || '科技区 UP 主',
  };
  configData.dubbing = {
    ...configData.dubbing,
    enabled: true,
    engine: $('#cfg-dub-engine').value,
    voice: $('#cfg-dub-voice').value,
    audio_mode: $('#cfg-dub-audio-mode').value,
    burn_narration_subtitles: true,
    timeline_mode: 'continuous',
    gpt_sovits: {
      ...(configData.dubbing?.gpt_sovits || {}),
      base_url: $('#cfg-gptsovits-url').value,
      reference_audio: $('#cfg-voice-clone-audio').value,
      prompt_text: $('#cfg-voice-clone-prompt').value,
    },
    voice_clone: {
      enabled: $('#cfg-dub-engine').value === 'gpt-sovits',
      reference_audio: $('#cfg-voice-clone-audio').value,
      prompt_text: $('#cfg-voice-clone-prompt').value,
    },
    azure: {
      ...((configData.dubbing || {}).azure || {}),
      key: $('#cfg-azure-key')?.value || '',
      region: $('#cfg-azure-region')?.value || 'eastasia',
    },
  };
  configData.smart_cut = {
    ...configData.smart_cut,
    enabled: $('#cfg-smart-cut-enabled').checked,
    target_duration_sec: parseInt($('#cfg-smart-cut-duration').value) || 90,
  };
  configData.vision = { ...(configData.vision || {}), enabled: $('#cfg-vision-enabled').checked };
  configData.broll = { ...(configData.broll || {}), enabled: $('#cfg-broll-enabled').checked };
  configData.i18n = { ...(configData.i18n || {}), enabled: $('#cfg-i18n-enabled').checked };
  configData.clip_short = {
    ...(configData.clip_short || {}),
    enabled: $('#cfg-short-enabled').checked,
    duration_sec: parseInt($('#cfg-short-duration').value) || 75,
    multi_clip_count: parseInt($('#cfg-multi-clip')?.value) || 1,
    bgm: {
      ...((configData.clip_short || {}).bgm || {}),
      enabled: $('#cfg-bgm-enabled').checked,
      file: $('#cfg-bgm-file').value,
      ducking: $('#cfg-bgm-ducking')?.checked !== false,
    },
  };
  configData.copy = configData.copy || {};
  configData.copy.general = {
    ...(configData.copy.general || {}),
    consistency_check: true,
    deduplicate_titles: true,
    title_scoring_enabled: true,
  };
  const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(configData) });
  const d = await r.json();
  toast(d.ok ? '配置已保存' : (d.error || '保存失败'), d.ok);
});

// ── Copy Config ──
async function loadCopyConfig() {
  if (!Object.keys(configData).length) {
    const r = await fetch('/api/config');
    configData = await r.json();
  }
  const copy = configData.copy || {};
  for (const platform of ['bilibili', 'xiaohongshu', 'douyin', 'wechat_mp']) {
    const pid = platform === 'wechat_mp' ? 'wechat' : platform;
    const el = $(`#copy-${pid}-enabled`);
    if (!el) continue;
    const pc = copy[platform] || {};
    el.checked = pc.enabled === true || (platform !== 'douyin' && platform !== 'wechat_mp' && pc.enabled !== false);
    const personaEl = $(`#copy-${pid}-persona`);
    if (personaEl) personaEl.value = pc.persona || '';
    const kwEl = $(`#copy-${pid}-keywords`);
    if (kwEl) kwEl.value = (pc.keywords || []).join(', ');
    if (platform === 'bilibili' || platform === 'xiaohongshu') {
      $(`#copy-${platform}-persona`).value = pc.persona || '';
      $(`#copy-${platform}-style`).value = pc.style || '';
      $(`#copy-${platform}-tone`).value = pc.tone || '';
      $(`#copy-${platform}-audience`).value = pc.audience || '';
      $(`#copy-${platform}-keywords`).value = (pc.keywords || []).join(', ');
      $(`#copy-${platform}-cta`).value = pc.call_to_action || '';
      if (platform === 'bilibili') {
        $(`#copy-${platform}-max-title`).value = pc.max_title_length ?? 40;
        $(`#copy-${platform}-max-desc`).value = pc.max_description_length ?? 500;
      } else {
        $(`#copy-${platform}-max-title`).value = pc.max_title_length ?? 20;
        $(`#copy-${platform}-max-body`).value = pc.max_body_length ?? 1000;
      }
    }
  }
  const gen = copy.general || {};
  $('#copy-hook-style').value = gen.short_hook_style || '痛点反问式';
  $('#copy-hook-count').value = gen.short_hook_count ?? 3;
  $('#copy-forbidden').value = (gen.global_forbidden_words || []).join(', ');
}

$('#save-copy-config').addEventListener('click', async () => {
  if (!configData.copy) configData.copy = {};
  for (const platform of ['bilibili', 'xiaohongshu', 'douyin', 'wechat_mp']) {
    const pid = platform === 'wechat_mp' ? 'wechat' : platform;
    const pc = configData.copy[platform] || {};
    const base = {
      ...pc,
      enabled: $(`#copy-${pid}-enabled`)?.checked ?? pc.enabled,
      persona: $(`#copy-${pid}-persona`)?.value || pc.persona,
      keywords: ($(`#copy-${pid}-keywords`)?.value || '').split(',').map(s => s.trim()).filter(Boolean),
    };
    if (platform === 'bilibili' || platform === 'xiaohongshu') {
      configData.copy[platform] = {
        ...base,
        style: $(`#copy-${platform}-style`).value,
        tone: $(`#copy-${platform}-tone`).value,
        audience: $(`#copy-${platform}-audience`).value,
        call_to_action: $(`#copy-${platform}-cta`).value,
        max_title_length: parseInt($(`#copy-${platform}-max-title`).value),
        ...(platform === 'bilibili'
          ? { max_description_length: parseInt($(`#copy-${platform}-max-desc`).value) }
          : { max_body_length: parseInt($(`#copy-${platform}-max-body`).value), emoji_usage: true, numbered_tips: true }),
      };
    } else {
      configData.copy[platform] = base;
    }
  }
  configData.copy.general = {
    ...configData.copy.general,
    short_hook_enabled: true,
    short_hook_style: $('#copy-hook-style').value,
    short_hook_count: parseInt($('#copy-hook-count').value),
    global_forbidden_words: $('#copy-forbidden').value.split(',').map(s => s.trim()).filter(Boolean),
  };
  const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(configData) });
  const d = await r.json();
  toast(d.ok ? '文案配置已保存' : (d.error || '保存失败'), d.ok);
});

// ── Init ──
async function loadTerminology() {
  const r = await fetch('/api/terminology');
  const d = await r.json();
  const lines = Object.entries(d.replacements || {}).map(([k, v]) => `${k} → ${v}`);
  $('#term-editor').value = lines.join('\n');
}

$('#save-terminology')?.addEventListener('click', async () => {
  const reps = {};
  $('#term-editor').value.split('\n').filter(Boolean).forEach(line => {
    const m = line.split(/→|->/);
    if (m.length >= 2) reps[m[0].trim()] = m.slice(1).join('->').trim();
  });
  const r = await fetch('/api/terminology', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ replacements: reps }) });
  const d = await r.json();
  toast(d.ok ? '术语表已保存' : (d.error || '失败'), d.ok);
});

async function loadAssets() {
  const r = await fetch('/api/assets');
  const items = await r.json();
  const el = $('#assets-list');
  if (!items.length) { el.innerHTML = '<div class="empty">暂无素材</div>'; return; }
  el.innerHTML = items.map(a => `<div class="file-tag" style="display:block;margin:6px 0">${a.kind}/${a.name} <code>${a.path}</code></div>`).join('');
}

async function uploadAsset(inputId, kind) {
  const inp = $(inputId);
  if (!inp?.files?.length) return;
  const fd = new FormData();
  fd.append('file', inp.files[0]);
  fd.append('kind', kind);
  const r = await fetch('/api/assets/upload', { method: 'POST', body: fd });
  const d = await r.json();
  toast(d.ok ? `已上传: ${d.path}` : (d.error || '失败'), d.ok);
  if (d.ok && kind === 'bgm') $('#cfg-bgm-file').value = d.path;
  if (d.ok && kind === 'voice') $('#cfg-voice-clone-audio').value = d.path;
  loadAssets();
}

$('#upload-bgm')?.addEventListener('change', () => uploadAsset('#upload-bgm', 'bgm'));
$('#upload-voice')?.addEventListener('change', () => uploadAsset('#upload-voice', 'voice'));
$('#upload-broll')?.addEventListener('change', () => uploadAsset('#upload-broll', 'broll'));

$('#btn-tts-test')?.addEventListener('click', async () => {
  const r = await fetch('/api/tts/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: '你好，这是配音测试。', engine: $('#cfg-dub-engine')?.value, voice: $('#cfg-dub-voice')?.value }),
  });
  if (r.headers.get('content-type')?.includes('audio')) {
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const aud = $('#tts-test-audio');
    aud.src = url;
    aud.style.display = 'block';
    aud.play();
    toast('试播成功');
  } else {
    const d = await r.json();
    toast(d.error || '试播失败', false);
  }
});

$('#save-auth-token')?.addEventListener('click', () => {
  localStorage.setItem('auth_token', ($('#auth-token-input')?.value || '').trim());
  toast('Token 已保存到浏览器');
});
if (localStorage.getItem('auth_token') && $('#auth-token-input')) {
  $('#auth-token-input').value = localStorage.getItem('auth_token');
}

loadStatus();
checkVersion();
connectWebSocket();

$('#import-config-file')?.addEventListener('change', async (ev) => {
  const file = ev.target.files?.[0];
  if (!file) return;
  const text = await file.text();
  const r = await fetch('/api/config/import?merge=true', { method: 'POST', body: text, headers: { 'Content-Type': 'text/yaml' } });
  const d = await r.json();
  toast(d.ok ? '配置已导入' : (d.error || '导入失败'), d.ok);
  if (d.ok) loadConfig();
  ev.target.value = '';
});

setInterval(() => {
  if (wsConnected) return;
  if ($('#page-jobs').classList.contains('active')) loadJobs();
  if ($('#page-dashboard').classList.contains('active')) loadStatus();
}, 5000);
