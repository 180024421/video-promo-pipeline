# Changelog

## v3.5.0

- README / DEPLOY 文档对齐；GitHub VERSION 远程升级检查
- `video_quality` 贯穿烧字幕、竖屏、花字等 FFmpeg 重编码步骤
- 首次使用 Web 向导 + 可选依赖一键安装 API
- B 站上传：分片重试、断点续传、bvid 链接、Web 重试按钮
- 抖音/小红书发布清单增强（manual_steps + clipboard）
- 热点话题：B 站热榜 API + LM 动态生成
- 字幕波形时间轴 + 色块拖拽校对
- CLI：`--from-step` / `--resume`；`run.ps1 -InstallOptional`
- 测试：Web API 冒烟 + v3.5 单元测试

## v3.4.0

- B 站 UPOS 分片上传 + Web 上传进度
- WebSocket 实时任务进度（`/ws/progress`）
- 从失败处继续 / 按步骤重跑（转写、粗剪、配音等）
- 按 job 分文件日志（`job.log`）
- 配置导入/导出、批量 watch_in 面板
- 成片质量预设（fast/balanced/quality）
- Whisper 模型说明 + GPU 缓存释放开关
- WhisperX 字级对齐、热点话题、封面 A/B、片头片尾
- 敏感词二次扫描、多语言字幕轨导出
- 竖屏多段 Web 并排预览
- `/api/health`、`/api/version`、GitHub Actions CI、用户手册

## v3.3.0

- Web Token 鉴权、LM 用量统计仪表盘
- 说话人分离（启发式 / 可选 pyannote）
- 人脸居中竖屏裁剪（opencv）
- 视觉剪辑人工确认、AB 双音色配音
- B 站 OAuth 上传准备（auto_upload）
- 插件系统、Docker GPU compose
- 字幕时间轴滑块编辑、E2E 打包测试

## v3.2.0

- 文案：标题去重、一致性检查、A/B 评分、B 站章节时间轴
- 竖屏：多段 AI 选片、BGM ducking、偏上裁剪
- 封面：从视频截帧 + 文字叠加
- Web：字幕校对、术语表、素材上传、任务删除、排队等待、日志/发布包 Tab
- GPU 队列改为 FIFO 阻塞排队
- 发布素材包 publish_pack.json

## v3.1.0

- 配置页补全：工作流预设、TTS 引擎、GPT-SoVITS、语音克隆、软字幕模式、BGM、智能剪辑等
- 任务详情 14 步流水线时间线 + 解说分段表格编辑器
- 上传预检 LM Studio；支持「仅转写」模式
- 长视频 Whisper 分块转写（>30 分钟自动切片）
- 软字幕导出（mp4 + srt 打包，不烧录）
- FFmpeg 下载重试 + 备用镜像
- GPU 任务队列（Web 并发限制）
- batch_watch 支持 `--preset`
- 仪表盘 GPT-SoVITS 连通性检查
- 静态资源 cache busting
- Docker / docker-compose 一键部署
