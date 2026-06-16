/** v3.9 UI extensions */
async function loadPublishStats() {
  const r = await fetch('/api/analytics/publish');
  const d = await r.json();
  const el = document.querySelector('#publish-stats');
  if (el) el.innerHTML = `总播放: <strong>${d.total_views||0}</strong> | 总赞: ${d.total_likes||0}`;
}
document.querySelector('#btn-ps-record')?.addEventListener('click', async () => {
  const body = {
    job: document.querySelector('#ps-job')?.value,
    platform: document.querySelector('#ps-platform')?.value,
    views: +(document.querySelector('#ps-views')?.value||0),
    likes: +(document.querySelector('#ps-likes')?.value||0),
  };
  await fetch('/api/analytics/publish', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (typeof toast === 'function') toast('已记录');
  loadPublishStats();
});

async function loadPreviewJobs() {
  const r = await fetch('/api/jobs');
  const jobs = await r.json();
  const html = '<option value="">选择任务...</option>' + (jobs||[]).map(j => `<option value="${j.name}">${j.name}</option>`).join('');
  const sel = document.querySelector('#preview-job');
  if (sel) sel.innerHTML = html;
  const cmp = document.querySelector('#compare-job');
  if (cmp) cmp.innerHTML = html;
}

document.querySelector('#btn-generate-hls')?.addEventListener('click', async () => {
  const job = document.querySelector('#preview-job')?.value;
  if (!job) return toast?.('请选择任务', false);
  const r = await fetch(`/api/jobs/${job}/hls`);
  const d = await r.json();
  if (d.playlist) {
    const player = document.querySelector('#preview-player');
    player.src = `/api/jobs/${job}/files/hls/index.m3u8`;
    player.style.display = 'block';
    player.play();
    toast?.(`HLS 已生成 ${d.segments} 段`);
  }
  const sr = await fetch(`/api/jobs/${job}/scenes`);
  const sd = await sr.json();
  const scenes = document.querySelector('#preview-scenes');
  if (scenes && sd.scenes) scenes.textContent = '场景: ' + sd.scenes.slice(0,20).map(s => s.time_sec+'s').join(' · ');
});

document.querySelector('#btn-enhance-audio')?.addEventListener('click', async () => {
  const job = document.querySelector('#preview-job')?.value;
  if (!job) return;
  const r = await fetch(`/api/jobs/${job}/enhance-audio`);
  const d = await r.json();
  toast?.(d.ok ? '音频增强完成' : (d.error||'失败'), d.ok);
});

let _editorSegs = [], _editorJob = '';
async function loadEditorJobs() {
  const r = await fetch('/api/jobs');
  const jobs = await r.json();
  const sel = document.querySelector('#editor-job');
  if (sel) sel.innerHTML = '<option value="">选择任务...</option>' + (jobs||[]).map(j => `<option value="${j.name}">${j.name}</option>`).join('');
}
function renderEditorSegs() {
  const box = document.querySelector('#editor-segments');
  if (!box) return;
  box.innerHTML = _editorSegs.map((s,i) => `<div style="border:1px solid var(--border);padding:6px;margin:4px 0">
    <b>#${i}</b> ${s.start}-${s.end}s <input value="${(s.text||'').replace(/"/g,'&quot;')}" data-i="${i}" class="seg-text-inp" style="width:70%">
    <button type="button" class="btn btn-secondary btn-sm seg-merge" data-i="${i}">合并下一段</button>
  </div>`).join('');
  box.querySelectorAll('.seg-merge').forEach(btn => btn.addEventListener('click', async () => {
    const i = +btn.dataset.i;
    await fetch(`/api/jobs/${_editorJob}/segments/${i}/merge/${i+1}`, { method: 'PUT' });
    document.querySelector('#btn-editor-load')?.click();
  }));
  box.querySelectorAll('.seg-text-inp').forEach(inp => inp.addEventListener('change', () => {
    _editorSegs[+inp.dataset.i].text = inp.value;
  }));
}
document.querySelector('#btn-editor-load')?.addEventListener('click', async () => {
  _editorJob = document.querySelector('#editor-job')?.value;
  if (!_editorJob) return;
  const r = await fetch(`/api/jobs/${_editorJob}/segments`);
  const d = await r.json();
  _editorSegs = d.segments || [];
  renderEditorSegs();
});
const saveBtn = document.createElement('button');
saveBtn.className = 'btn btn-primary btn-sm';
saveBtn.textContent = '保存字幕';
saveBtn.style.marginLeft = '8px';
saveBtn.onclick = async () => {
  if (!_editorJob) return;
  await fetch(`/api/jobs/${_editorJob}/segments`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({segments:_editorSegs}) });
  toast?.('已保存');
};
document.querySelector('#page-editor .form-row')?.appendChild(saveBtn);

async function loadFinetuneDeep() {
  const r = await fetch('/api/finetune-bridge/deep');
  const d = await r.json();
  const el = document.querySelector('#finetune-deep-status');
  if (el) el.textContent = `反馈 ${d.feedback_count} 条 | 可训练: ${d.ready_to_finetune?'是':'否'}`;
}
document.querySelector('#btn-export-finetune')?.addEventListener('click', async () => {
  const r = await fetch('/api/finetune-bridge/export-feedback', { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
  const d = await r.json();
  toast?.(d.count ? `导出 ${d.count} 条` : '无数据', !!d.count);
});
async function loadBatchDag() {
  const r = await fetch('/api/batch/plan');
  const d = await r.json();
  const el = document.querySelector('#batch-dag-status');
  if (el) el.innerHTML = (d.nodes||[]).map(n => `${n.status}: ${n.video.split(/[/\\\\]/).pop()}`).join('<br>') || '暂无';
}
document.querySelector('#btn-batch-plan')?.addEventListener('click', async () => {
  await fetch('/api/batch/plan/from-watch', { method:'POST' });
  loadBatchDag();
});
document.querySelector('#btn-batch-run')?.addEventListener('click', async () => {
  const r = await fetch('/api/batch/plan/run-next', { method:'POST' });
  const d = await r.json();
  toast?.(d.ok ? `启动 ${d.job_name}` : d.detail, d.ok);
});
async function loadPipelineDag() {
  const r = await fetch('/api/pipeline-dag');
  const d = await r.json();
  const dag = JSON.parse(d.dag||'{}');
  const el = document.querySelector('#pipeline-dag-viz');
  if (el) el.innerHTML = (dag.edges||[]).map(e => `${e.from} → ${e.to}`).join('<br>');
}
let _tenantId = localStorage.getItem('vpp-tenant') || '';
async function loadTenantInfo() {
  const r = await fetch('/api/tenant', { headers: _tenantId ? {'X-Tenant-ID': _tenantId} : {} });
  const d = await r.json();
  const el = document.querySelector('#tenant-info');
  if (el) el.textContent = `工作区: ${d.current||'默认'} | ${d.base}`;
}
document.querySelector('#btn-set-tenant')?.addEventListener('click', () => {
  _tenantId = document.querySelector('#tenant-id-input')?.value.trim() || '';
  localStorage.setItem('vpp-tenant', _tenantId);
  loadTenantInfo();
});
document.querySelector('#compare-job')?.addEventListener('change', async () => {
  const job = document.querySelector('#compare-job')?.value;
  if (!job) return;
  const r = await fetch(`/api/jobs/${job}/variants`);
  const d = await r.json();
  const box = document.querySelector('#compare-players');
  if (box) box.innerHTML = (d.variants||[]).slice(0,4).map(v =>
    `<div><small>${v.label}</small><video controls style="width:100%" src="/api/jobs/${job}/files/${v.path}"></video></div>`
  ).join('');
});

document.querySelectorAll('.nav-item').forEach(el => {
  el.addEventListener('click', () => {
    const p = el.dataset.page;
    if (p === 'tools') { loadFinetuneDeep(); loadBatchDag(); loadPipelineDag(); loadTenantInfo(); loadPreviewJobs(); }
    if (p === 'publish-stats') loadPublishStats();
    if (p === 'preview') loadPreviewJobs();
    if (p === 'editor') loadEditorJobs();
  });
});
