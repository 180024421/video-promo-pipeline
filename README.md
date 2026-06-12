# video-promo-pipeline v3.3

本地录屏视频 AI 推广流水线：**转写 → 智能剪辑 → AI 配音 → 烧字幕/软字幕 → 竖屏切片 → 多平台文案**。

Web 面板支持 **FFmpeg 一键安装**、工作流预设、14 步进度时间线、分步重跑、Docker 部署。

### v3.3 新增

- API Token 鉴权、LM 用量统计
- 说话人标注、人脸竖屏裁剪、视觉方案确认
- AB 双音色、B 站 OAuth 上传、插件 hook、Docker GPU

### v3.2 新增

- 字幕 Web 校对、术语表、素材库上传、任务删除、排队等待
- 多段竖屏、BGM ducking、视频截帧封面
- 标题去重/评分、B 站章节、发布素材包一键复制

### v3.1 新增

- 配置页：预设、TTS 引擎、GPT-SoVITS、软字幕模式、BGM、长视频分块转写
- 任务详情：流水线步骤时间线 + 解说分段表格编辑
- 上传 LM Studio 预检 +「仅转写」模式
- GPU 任务队列、`batch_watch --preset`

## 功能一览

| 步骤 | 工具 | 说明 |
|------|------|------|
| 环境检查 | preflight | FFmpeg / faster-whisper / LM Studio |
| 自动字幕 | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | SRT + VTT + ASS + segments.json |
| 术语纠错 | terminology.yaml | 转写后批量替换（ADB、Spring Boot 等） |
| 字幕后处理 | 内置 | 去口气、短句合并、自动换行 |
| 粗剪 | [auto-editor](https://github.com/WyattBlue/auto-editor) | 删除长静音 |
| **智能剪辑** | LM Studio | AI 规划高光片段（参考 ToonFlow/NarratoAI） |
| **AI 配音** | LM Studio + Edge-TTS | 解说稿生成 + 自动配音 |
| 烧字幕 | FFmpeg | 硬字幕成片（支持配音字幕） |
| 竖屏切片 | FFmpeg | 9:16 短视频片段（小红书/抖音） |
| 文案 | LM Studio OpenAI API | 多平台文案（B站、小红书、抖音、公众号） |
| 封面 | Pillow | 简易文字封面图 |
| 断点续跑 | pipeline.resume | 已有中间产物则跳过 |
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

# 4. 处理视频（基础：字幕+粗剪+文案）
.\run.ps1 -Video "D:\recordings\your_video.mp4"

# 5. 开启 AI 配音解说（需先在 config.yaml 设置 narration.enabled: true）
.\run.ps1 -Video "D:\recordings\your_video.mp4"
```

## 输出目录

每次任务在 `output/<视频名>_<时间戳>/`：

```
output/demo_20260611_203000/
  demo.mp4                           # 原片备份
  demo_cut.mp4                       # 粗剪后
  demo_cut_subtitled.mp4             # 硬字幕成片
  demo_cut_subtitled_short_1920p.mp4 # 竖屏切片
  subtitle.srt / .vtt / .ass
  transcript.txt
  segments.json
  promo_copy.json                    # 全平台文案 JSON
  promo_copy.md                      # Markdown 汇总
  bilibili_description.txt           # B 站简介（直接粘贴）
  xiaohongshu_post.txt               # 小红书正文（直接粘贴）
  cover.png
  narration.json                   # AI 解说稿（开启 narration 时）
  narration.srt                    # 配音字幕
  narration_audio.mp3              # 合成配音音轨
  *_dubbed.mp4                     # 配音成片
  summary.json
```

## 常用命令

```powershell
# 完整流程
.\run.ps1 -Video demo.mp4

# 只转写字幕（不占 LM Studio GPU）
.\run.ps1 -Video demo.mp4 -OnlyTranscribe

# 跳过粗剪和烧录，只要字幕+文案
.\run.ps1 -Video demo.mp4 -SkipCut -SkipBurn

# 运行时覆盖文案配置
.\run.ps1 -Video demo.mp4 -Persona "资深后端开发" -Topic "Spring Boot 3 实战" -Keywords "Java,微服务,接口测试" -Tone "专业严谨"

# 只生成 B 站文案
.\run.ps1 -Video demo.mp4 -OnlyPlatform "bilibili" -HookStyle "数字式"

# 跳过配音，只要字幕
.\run.ps1 -Video demo.mp4 -SkipDub

# 断点续跑（默认开启）
.\run.ps1 -Video demo.mp4 -JobDir output\demo_20260611_203000

# 强制全部重做
.\run.ps1 -Video demo.mp4 -JobDir output\demo_xxx -Force

# 仅重新生成文案
.\run.ps1 -OnlyCopy -JobDir output\demo_20260611_203000 -Persona "游戏自动化测试工程师"

# 监控目录批量处理
.\run.ps1 -Watch

# Web 面板 http://127.0.0.1:8766
.\run.ps1 -Web
```

## 配置体系详解

### 复制示范配置

```powershell
copy config.example.yaml config.yaml
copy terminology.example.yaml terminology.yaml
```

### AI 配音解说 (`config.yaml` → `narration` + `dubbing`)

参考 [ToonFlow](https://github.com/HBAI-Ltd/Toonflow-app) / [NarratoAI](https://github.com/linyqh/NarratoAI) 工作流：**转写 → LM 写解说稿 → TTS 配音 → 烧字幕**。

```yaml
narration:
  enabled: true                  # 开启 AI 配音流水线
  mode: commentary               # commentary=解说改写 | read_aloud=润色口播 | summarize=浓缩
  style: "专业解说，口语化"
  persona: "科技区 UP 主"
  use_lm: true                   # false=直接用转写文本配音

dubbing:
  voice: zh-CN-YunxiNeural       # Edge-TTS 音色
  timeline_mode: continuous      # continuous=连续朗读 | segment=按时间轴
  audio_mode: replace            # replace=替换原声 | mix=混音 | keep_original
  burn_narration_subtitles: true
```

### 智能剪辑 (`config.yaml` → `smart_cut`)

```yaml
smart_cut:
  enabled: true
  target_duration_sec: 90          # 剪成 90 秒精华版
```

### LM Studio 配置 (`config.yaml` → `lm_studio`)

```yaml
lm_studio:
  enabled: true
  base_url: http://127.0.0.1:1234/v1
  api_key: lm-studio
  model: ""               # 留空使用当前加载的模型
  temperature: 0.7
  max_tokens: 4096        # 单次最大输出 token
  timeout: 120            # 请求超时秒数
  max_retries: 3          # 失败重试次数
  json_retry: true        # JSON 解析失败自动重试
  system_prompt: ""       # 全局系统提示词
```

### 推广文案配置 (`config.yaml` → `copy`)

**四大平台独立配置**，每个平台都有：

| 配置项 | 说明 |
|--------|------|
| `persona` | 人设身份 |
| `style` | 内容风格（如"笔记体""干货分享"） |
| `tone` | 语气（如"亲切幽默""专业严谨"） |
| `audience` | 目标受众 |
| `keywords` | 关键词列表（注入 Prompt） |
| `max_title_length` | 标题最大字数 |
| `max_description_length` | 简介/正文最大字数 |
| `emoji_usage` | 是否使用 emoji |
| `call_to_action` | 行动号召语 |
| `forbidden_words` | 该平台专属禁用词 |
| `prompt_override` | 完全覆盖默认 Prompt（高级） |

**通用配置** (`copy.general`)：

| 配置项 | 说明 |
|--------|------|
| `short_hook_enabled` | 是否生成前三秒钩子 |
| `short_hook_style` | 钩子风格：痛点反问式 / 结果前置式 / 悬念式 / 数字式 / 对比式 |
| `short_hook_count` | 生成几个钩子候选 |
| `global_forbidden_words` | 全平台禁用词 |
| `transcript_max_length` | 送入 LM 的最大字符数 |

示例配置片段：

```yaml
copy:
  bilibili:
    enabled: true
    persona: "Java 全栈与自动化测试工程师"
    style: "干货分享 + 项目复盘"
    tone: "专业且接地气，不说教"
    audience: "后端开发、测试工程师、计算机专业学生"
    keywords: ["Java", "Spring Boot", "测试自动化"]
    max_title_length: 40
    max_description_length: 500
    emoji_usage: false
    call_to_action: "三连+关注，持续更新脱敏项目实战"
    forbidden_words: ["外挂", "搬砖", "挂机赚钱"]

  xiaohongshu:
    enabled: true
    persona: "从后端开发转型技术博主的 UP"
    style: "笔记体，像给朋友发消息"
    tone: "亲切、真诚、带点幽默"
    audience: "想搞副业的程序员"
    keywords: ["程序员副业", "自动化测试", "远程接单"]
    max_title_length: 20
    max_body_length: 1000
    emoji_usage: true
    emoji_set: ["💻", "🔥", "⚡", "📌", "✅", "🎯", "🚀"]
    numbered_tips: true
    highlight_boxes: true
    call_to_action: "关注我，持续分享程序员搞钱干货"

  douyin:
    enabled: false

  wechat_mp:
    enabled: false

  general:
    short_hook_enabled: true
    short_hook_style: "痛点反问式"
    short_hook_count: 3
    global_forbidden_words: ["外挂", "破解", "盗版", "黑产"]
```

### CLI 运行时覆盖

无需改配置文件，命令行直接覆盖：

```powershell
.\run.ps1 -Video demo.mp4 `
  -Persona "游戏自动化专家" `
  -Topic "ADB 多开自动化测试" `
  -Keywords "ADB,YOLO,自动化测试,游戏测试" `
  -Tone "活泼幽默" `
  -Style "实战教程" `
  -OnlyPlatform "bilibili" `
  -HookStyle "悬念式" `
  -Forbidden "破解,外挂,作弊"
```

参数映射：

| CLI 参数 | 覆盖配置 |
|----------|----------|
| `-Persona` | copy.*.persona |
| `-Topic` | copy.*.content_type |
| `-Style` | copy.*.style |
| `-Tone` | copy.*.tone |
| `-Keywords` | copy.*.keywords |
| `-Forbidden` | copy.general.global_forbidden_words（追加） |
| `-Platforms` / `-OnlyPlatform` | 控制启用哪些平台 |
| `-HookStyle` | copy.general.short_hook_style |

## 显存建议（4060 Ti 8G）

1. **不要同时**开 Whisper（GPU）和 LM Studio 大模型。
2. 推荐：先 `-OnlyTranscribe` 跑字幕 → 关闭后再生成文案。
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
