# 用户手册

> 版本 **v3.8.0**

## v3.8 新功能

- **子进程任务**：`web.use_subprocess_pipeline: true`，强制停止可 kill GPU 子进程
- **Redis Worker**：`distributed.redis_url` + `python worker.py`
- **离线降级**：无 LM Studio 时自动跳过文案/智能剪辑/配音
- **RAG 向量**：`rag.use_vectors: true`，可选 `sentence-transformers`
- **发布预审**：任务详情或 `GET /api/jobs/{name}/preflight`
- **模板市场**：工具页一键应用工作流/Prompt/竖屏模板
- **数据看板**：侧栏「数据看板」查看发布链接与日历
- **Playwright 半自动**：`browser_publish.enabled` + API 触发
- **团队 Token**：`team.enabled` + `/api/team/tokens`

## 快速开始

```powershell
.\run.ps1 -Setup
.\run.ps1 -Web
```

浏览器：http://127.0.0.1:8766 · API 文档：http://127.0.0.1:8766/docs

## 服务安装

```powershell
.\scripts\install-service.ps1
```
