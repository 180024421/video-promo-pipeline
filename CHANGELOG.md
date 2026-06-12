# Changelog

## [2.0.0] - 2026-06-11

### Added
- 术语纠错（`terminology.yaml`）
- 字幕后处理：去口气、短句合并、自动换行
- 多格式字幕导出：VTT、ASS
- 竖屏短视频切片（`clip_short`）
- 封面图生成（`cover`）
- 平台化文案 prompt（`prompts/bilibili_java.md` 等）
- 章节摘要注入文案生成
- LM Studio JSON 解析失败自动重试
- `bilibili_description.txt` / `xiaohongshu_post.txt` 直出
- 断点续跑（`pipeline.resume`）
- CLI：`--only-transcribe`、`--only-copy`、`--job-dir`、`--preflight`、`--force`
- 批量监控 `batch_watch.py`
- 简易 Web 面板 `web_app.py`
- 环境预检 `preflight.py`
- 单元测试 `tests/`

### Changed
- `pipeline.py` 集成全部子模块
- `config.example.yaml` 扩展配置项
- `run.ps1` 支持 Watch / Web / Preflight

## [1.0.0] - 2026-06-11

- 首版：Whisper 转写 → Auto-Editor 粗剪 → FFmpeg 烧录 → LM Studio 文案
