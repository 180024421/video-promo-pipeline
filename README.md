# video-promo-pipeline v3.8

本地录屏视频 AI 推广流水线：**转写 → 智能剪辑 → AI 配音 → 烧字幕/软字幕 → 竖屏切片 → 多平台文案 → 发布**。

Web 面板：http://127.0.0.1:8766（子进程任务、数据看板、模板市场、发布预审）

### v3.8 新增

- 子进程 kill、Redis Worker、离线降级、RAG 向量检索
- 发布预审、任务对比、A/B 回流、Playwright 半自动发布
- YouTube/视频号/快手、模板市场、团队 Token

### v3.7 回顾

- 定时发布自动执行、运行中任务强制停止
- Whisper 热词、成片质检、章节导出、竖屏平台模板
- 耗时/LM 成本仪表盘、RAG 知识库、备份恢复、批量 HTML 报告

### v3.6 回顾

- NVENC 编码、步骤耗时统计、队列暂停/取消/优先级
- 通知（Webhook/企微/邮件）、审计日志与 API 限流
- 剪映导出、Prompt 模板、AI 选封面、BGM 节拍对齐
- B 站 OAuth、定时发布、多账号矩阵、半自动发布包
- 任务备份、用户插件、术语建议、`start-web.cmd`

### v3.5 回顾

- 成片质量预设全链路生效（烧字幕 / 竖屏 / 花字）
- 首次使用向导 + 可选依赖一键安装（WhisperX / OpenCV / pyannote 等）
- B 站分片上传重试 / 断点续传 / bvid 链接
- 抖音 & 小红书发布清单（步骤 + 一键复制）
- 热点话题：B 站热榜 + LM 动态生成
- 字幕波形时间轴 + 拖拽色块校对
- CLI `--from-step` / `--resume`；`run.ps1 -InstallOptional`
- 部署文档 [docs/DEPLOY.md](docs/DEPLOY.md)（Nginx / Caddy / HTTPS）

### v3.4 回顾

WebSocket 进度、从失败处继续、配置导入导出、分任务日志、GitHub Actions CI

完整用户手册：[docs/USER_GUIDE.md](docs/USER_GUIDE.md)

## 功能一览

| 步骤 | 工具 | 说明 |
|------|------|------|
| 环境检查 | preflight + 向导 | FFmpeg / Whisper / LM Studio |
| 自动字幕 | faster-whisper | SRT + VTT + ASS + 可选 WhisperX |
| 粗剪 | auto-editor | 删除长静音 |
| 智能剪辑 | LM Studio | AI 规划高光片段 |
| AI 配音 | LM + Edge-TTS | 解说稿 + TTS |
| 烧字幕 | FFmpeg | 硬字幕 / 软字幕包 |
| 竖屏 | FFmpeg | 多段竖屏 + BGM ducking |
| 文案 | LM Studio | B站 / 小红书 / 抖音 / 公众号 |
| 发布 | manifest + B站 API | 分片上传 + 多平台清单 |
| Web | web_app.py | 上传、任务、配置、波形校对 |

## 快速开始

```powershell
cd video-promo-pipeline
.\run.ps1 -Setup
.\run.ps1 -Web
# 浏览器打开 http://127.0.0.1:8766
```

```powershell
# 处理单个视频
.\run.ps1 -Video "D:\recordings\demo.mp4"

# 从失败步骤继续
python process.py --job-dir output\xxx --resume

# 从指定步骤继续
python process.py --job-dir output\xxx --from-step transcribe

# 安装可选依赖
.\run.ps1 -InstallOptional
```

## 配置

复制 `config.example.yaml` → `config.yaml`，Web 面板可导入/导出。

关键项：

- `whisper.model` / `whisper.clear_gpu_cache`
- `video_quality.preset`: fast | balanced | quality
- `web.auth_token`（公网部署务必设置）
- `publish.bilibili` OAuth + `auto_upload`

## 部署

见 [docs/DEPLOY.md](docs/DEPLOY.md)：局域网 `0.0.0.0`、Nginx 反代、Caddy HTTPS、Docker。

## 测试

```powershell
python -m pytest tests/ -q
```

## 许可

MIT
