# video-promo-pipeline

本地录屏视频的推广流水线：**自动字幕（Whisper）→ 粗剪去静音（Auto-Editor）→ 烧录字幕（FFmpeg）→ 推广文案（LM Studio）**。

面向技术向 UP 主（B 站 / 小红书）：你自己录屏，工具负责后半段。

## 功能

| 步骤 | 工具 | 说明 |
|------|------|------|
| 自动字幕 | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | GPU/CPU 本地转写，输出 SRT + 全文 |
| 粗剪 | [auto-editor](https://github.com/WyattBlue/auto-editor) | 删除长静音、口气 |
| 烧字幕 | FFmpeg | 硬字幕成片 |
| 文案 | LM Studio OpenAI API | B 站标题/简介/标签 + 小红书正文 |

## 环境要求

- Windows 10/11（PowerShell）
- Python 3.10+
- **FFmpeg**（加入 PATH）
- **NVIDIA GPU**（可选，推荐；4060 Ti 8G 建议 Whisper `small` 或 `medium`）
- **LM Studio**（文案步骤；需开启 Local Server，默认 `http://127.0.0.1:1234`）

## 快速开始

```powershell
cd video-promo-pipeline

# 1. 安装依赖
.\run.ps1 -Setup

# 2. 编辑 config.yaml（从 config.example.yaml 复制）
#    - whisper.model: 8G 显存建议 small 或 medium
#    - lm_studio.base_url: LM Studio 地址

# 3. 启动 LM Studio，加载 Qwen2.5-7B-Instruct 等模型，开启 Local Server

# 4. 处理视频
.\run.ps1 -Video "D:\recordings\your_video.mp4"
```

## 输出目录

每次任务在 `output/<视频名>_<时间戳>/` 下生成：

```
output/demo_20260611_203000/
  demo.mp4              # 原片备份
  demo_cut.mp4          # 粗剪后（若启用）
  demo_cut_subtitled.mp4 # 带硬字幕成片
  subtitle.srt
  transcript.txt
  segments.json
  promo_copy.json
  promo_copy.md         # 可直接复制发布的文案
  summary.json
```

## 命令行参数

```powershell
# 只转写+文案，不粗剪、不烧字幕
.\run.ps1 -Video demo.mp4 -SkipCut -SkipBurn

# 不调用 LM Studio（仅字幕）
.\run.ps1 -Video demo.mp4 -SkipCopy

# 已有 transcript.txt，单独生成文案
python generate_copy.py output\xxx\transcript.txt
```

## 显存建议（4060 Ti 8G）

1. **不要同时**开 Whisper（GPU）和 LM Studio 大模型。
2. 推荐顺序：先跑本工具转写 → 关闭后再用 LM Studio 生成文案。
3. `config.yaml` 中 `whisper.model: small` 或 `medium`，`compute_type: float16`。

## LM Studio 配置

1. 加载模型（如 Qwen2.5-7B-Instruct Q4）
2. 左侧 **Developer** → **Local Server** → Start Server
3. `config.yaml`：

```yaml
lm_studio:
  base_url: http://127.0.0.1:1234/v1
  api_key: lm-studio
  model: ""   # 留空使用当前加载模型
```

## 免责声明

- 生成文案请人工审核后再发布
- 请勿在文案中包含违规导流、外挂相关表述
- 视频素材请使用你有权展示的内容

## License

MIT
