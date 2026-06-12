# 故障排查

## FFmpeg 未找到

**现象**：`未找到 ffmpeg，请安装并加入 PATH`

**处理**：
1. 从 https://ffmpeg.org/download.html 或 `winget install ffmpeg` 安装
2. 新开 PowerShell，`ffmpeg -version` 能执行即可
3. 或在 `config.yaml` 填写绝对路径：`ffmpeg.path: C:\ffmpeg\bin\ffmpeg.exe`

## faster-whisper / CUDA 报错

**现象**：`CUDA out of memory` 或加载模型失败

**处理**：
1. `whisper.model` 改为 `small` 或 `base`
2. 关闭 LM Studio 与其他占 GPU 程序
3. 临时改用 CPU：`device: cpu`，`compute_type: int8`

## LM Studio 连接失败

**现象**：`LM Studio 未就绪` 或文案步骤超时

**处理**：
1. LM Studio → Developer → Local Server → Start
2. 确认 `lm_studio.base_url` 为 `http://127.0.0.1:1234/v1`
3. 先 `-SkipCopy` 跑完字幕，再单独 `.\run.ps1 -OnlyCopy -JobDir output\xxx`

## 文案 JSON 解析失败

**现象**：`promo_copy.json` 只有 `raw` 字段

**处理**：
1. 换更小、更听话的 Instruct 模型（Qwen2.5-7B）
2. 保持 `lm_studio.json_retry: true`
3. 检查 `prompts/*.md` 是否被正确 `prompt_file` 引用

## Auto-Editor 跳过

**现象**：`未找到 auto-editor，跳过粗剪`

**处理**：`pip install auto-editor`，或 `config.yaml` 设 `auto_editor.enabled: false`

## 断点续跑用了旧结果

**处理**：加 `-Force` 强制重做，或删除任务目录内对应中间文件（如 `segments.json`）

## Web 面板无法访问

**处理**：
1. `pip install -r requirements-web.txt`
2. `.\run.ps1 -Web`，浏览器打开 http://127.0.0.1:8766
3. 检查防火墙是否拦截本机端口

## 竖屏切片画面被裁切过多

**处理**：调整 `clip_short.position`：`start` / `middle` / `chapter_first`
