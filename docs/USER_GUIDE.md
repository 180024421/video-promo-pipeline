# 用户手册

> 版本 **v3.5.0** — 部署见 [DEPLOY.md](DEPLOY.md)

## 快速开始

1. 复制 `config.example.yaml` 为 `config.yaml`
2. 安装依赖：`pip install -r requirements.txt`
3. 启动 Web 面板：`python web_app.py` 或 `.\run.ps1 -Web`
4. 浏览器打开 http://127.0.0.1:8766

## 核心流程

上传录屏 → Whisper 转写 → 粗剪/智能剪辑 → LM 解说稿 → TTS 配音 → 烧字幕 → 竖屏切片 → 多平台文案 → 封面 → 打包发布

## v3.5 新功能

- **首次使用向导**：仪表盘自动显示待办步骤
- **可选依赖**：`POST /api/optional-deps/install` 或 `.\run.ps1 -InstallOptional`
- **波形字幕校对**：任务详情 → 字幕校对 Tab，拖拽色块调整起止
- **B 站上传重试**：发布 Tab → 重试/续传
- **CLI 续跑**：`python process.py --job-dir output\xxx --resume`

## v3.4 新功能

### 从失败处继续
任务详情点击 **「从失败处继续」**，或重跑指定步骤（转写/粗剪/配音/字幕等）。

### WebSocket 实时进度
面板自动连接 `/ws/progress`，任务进度实时更新（无 WebSocket 时回退 5 秒轮询）。

### 批量任务
将视频放入 `watch_in/`，在 **批量任务** 页点击「处理下一个」。

### B 站分片上传
配置 `publish.bilibili` 的 OAuth 凭证并开启 `auto_upload: true`。进度写入 `bilibili_upload_progress.json`，Web 任务详情可查看。

### 配置导入/导出
配置页可导出 YAML、从文件导入（合并或覆盖）。

### 成片质量预设
`video_quality.preset`: `fast` | `balanced` | `quality`

### 可选增强
- **WhisperX 字级对齐**：`whisperx.enabled: true`（需 `pip install whisperx`）
- **热点话题注入**：`hot_topics.enabled: true`
- **封面 A/B**：`cover.ab_enabled: true`
- **片头片尾**：`intro_outro.enabled: true`
- **敏感词二次扫描**：`sensitive_scan.enabled: true`
- **多语言成片**：`i18n.enabled` + `i18n.export_video: true`

## API

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 健康检查 |
| `GET /api/version` | 版本与升级提示 |
| `GET /api/config/export` | 导出配置 |
| `POST /api/config/import` | 导入配置 |
| `GET /api/batch/watch` | 批量队列 |
| `WS /ws/progress` | 实时任务进度 |

## 鉴权

在 `config.yaml` 设置 `web.auth_token` 后，API 需请求头 `X-Auth-Token`；WebSocket 用 `?token=` 查询参数。

## 故障排查

- **FFmpeg 未就绪**：仪表盘一键安装
- **LM Studio 未连接**：启动 LM Studio 并加载模型
- **GPU 显存不足**：Whisper 改用 `small`，或开启 `whisper.clear_gpu_cache`
- **任务失败**：查看任务详情「日志」Tab（`job.log`）
