# video-promo-pipeline

本地录屏视频的推广流水线 v2：**自动字幕 → 术语纠错 → 粗剪 → 烧录 → 竖屏切片 → LM Studio 文案 → 封面图**。

面向技术向 UP 主（B 站 / 小红书）：你自己录屏，工具负责后半段。

## 功能一览

| 步骤 | 工具 | 说明 |
|------|------|------|
| 环境检查 | preflight | FFmpeg / faster-whisper / LM Studio |
| 自动字幕 | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | SRT + VTT + ASS + segments.json |
| 术语纠错 | terminology.yaml | 转写后批量替换（ADB、Spring Boot 等） |
| 字幕后处理 | 内置 | 去口气、短句合并、自动换行 |
| 粗剪 | [auto-editor](https://github.com/WyattBlue/auto-editor) | 删除长静音 |
| 烧字幕 | FFmpeg | 硬字幕成片 |
| 竖屏切片 | FFmpeg | 9:16 短视频片段（小红书） |
| 文案 | LM Studio OpenAI API | B 站标题/简介/标签 + 小红书正文 |
| 封面 | Pillow | 简易文字封面图 |
| 断点续跑 | pipeline.resume | 已有 segments / 成片 / 文案则跳过 |
| 批量监控 | batch_watch.py | 放入 `watch_in/` 自动处理 |
| Web 面板 | web_app.py | 上传视频、查看任务列表 |

## 环境要求

- Windows 10/11（PowerShell）
- Python 3.10+
- **FFmpeg**（加入 PATH）
- **NVIDIA GPU**（可选；4060 Ti 8G 建议 Whisper `small`）
- **LM Studio**（文案步骤；Local Server 默认 `http://127.0.0.1:1234`）

## 快速开始

```powershell
cd video-promo-pipeline

# 1. 安装依赖 + 生成 config.yaml / terminology.yaml
.\run.ps1 -Setup

# 2. 检查环境
.\run.ps1 -Preflight

# 3. 启动 LM Studio，加载 Qwen2.5-7B-Instruct 等，开启 Local Server

# 4. 处理视频
.\run.ps1 -Video "D:\recordings\your_video.mp4"
```

## 输出目录

每次任务在 `output/<视频名>_<时间戳>/`：

```
output/demo_20260611_203000/
  demo.mp4                  # 原片备份
  demo_cut.mp4              # 粗剪后
  demo_cut_subtitled.mp4    # 硬字幕成片
  demo_cut_subtitled_short_1920p.mp4  # 竖屏切片
  subtitle.srt / .vtt / .ass
  transcript.txt
  segments.json
  promo_copy.json / .md
  bilibili_description.txt  # 可直接粘贴 B 站简介
  xiaohongshu_post.txt      # 可直接粘贴小红书
  cover.png
  summary.json
```

## 常用命令

```powershell
# 只转写字幕（不占 LM Studio）
.\run.ps1 -Video demo.mp4 -OnlyTranscribe

# 跳过粗剪和烧录，只要字幕+文案
.\run.ps1 -Video demo.mp4 -SkipCut -SkipBurn

# 断点续跑（默认开启，使用已有中间产物）
.\run.ps1 -Video demo.mp4 -JobDir output\demo_20260611_203000

# 强制全部重做
.\run.ps1 -Video demo.mp4 -JobDir output\demo_xxx -Force

# 仅重新生成文案（任务目录已有 transcript.txt）
.\run.ps1 -OnlyCopy -JobDir output\demo_20260611_203000

# 监控目录批量处理
.\run.ps1 -Watch

# Web 面板 http://127.0.0.1:8766
.\run.ps1 -Web
```

## 配置要点

复制 `config.example.yaml` → `config.yaml`，复制 `terminology.example.yaml` → `terminology.yaml`。

```yaml
whisper:
  model: small          # 4060Ti 8G 建议 small；勿与 LM Studio 同时占 GPU

copy:
  persona: "Java 全栈与自动化测试工程师"
  prompt_file: prompts/bilibili_java.md   # 或 bilibili_game.md
  platforms: [bilibili, xiaohongshu]

pipeline:
  resume: true          # 断点续跑
  copy_source_video: false
```

## 显存建议（4060 Ti 8G）

1. **不要同时**开 Whisper（GPU）和 LM Studio 大模型。
2. 推荐：先 `-OnlyTranscribe` 或 `-SkipCopy` 跑字幕 → 关闭后再生成文案。
3. `whisper.model: small`，`compute_type: float16`。

## 测试

```powershell
.\.venv\Scripts\Activate.ps1
pytest tests/ -q
```

## 故障排查

见 [docs/troubleshooting.md](docs/troubleshooting.md)。

## 免责声明

- 生成文案请人工审核后再发布
- 请勿在文案中包含违规导流、外挂相关表述
- 视频素材请使用你有权展示的内容

## License

MIT
