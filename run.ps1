# 一键处理录屏视频 v2
# 用法:
#   .\run.ps1 -Setup
#   .\run.ps1 -Video "D:\recordings\demo.mp4"
#   .\run.ps1 -Preflight
#   .\run.ps1 -Watch
#   .\run.ps1 -Web

param(
    [string]$Video = "",
    [string]$JobDir = "",
    [switch]$SkipCut,
    [switch]$SkipBurn,
    [switch]$SkipCopy,
    [switch]$SkipDub,
    [switch]$OnlyDub,
    [switch]$OnlyBurn,
    [switch]$OnlyShort,
    [switch]$OnlyPack,
    [string]$Preset = "",
    [switch]$OnlyTranscribe,
    [switch]$OnlyCopy,
    [switch]$Force,
    [switch]$Preflight,
    [switch]$Setup,
    [switch]$Watch,
    [switch]$Web,
    # 运行时文案覆盖
    [string]$Persona = "",
    [string]$Topic = "",
    [string]$Style = "",
    [string]$Tone = "",
    [string]$Keywords = "",
    [string]$Forbidden = "",
    [string]$Platforms = "",
    [string]$OnlyPlatform = "",
    [string]$HookStyle = ""
)

$Root = $PSScriptRoot
Set-Location $Root

if ($Setup) {
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pip install -r requirements-web.txt
    pip install pytest
    if (-not (Test-Path "config.yaml")) {
        Copy-Item "config.example.yaml" "config.yaml"
    }
    if (-not (Test-Path "terminology.yaml")) {
        Copy-Item "terminology.example.yaml" "terminology.yaml"
    }
    New-Item -ItemType Directory -Force -Path "watch_in" | Out-Null
    Write-Host "环境安装完成。请安装 FFmpeg 并加入 PATH，启动 LM Studio Local Server。"
    exit 0
}

if (-not (Test-Path ".venv")) {
    Write-Host "请先运行: .\run.ps1 -Setup"
    exit 1
}

.\.venv\Scripts\Activate.ps1

if ($Preflight) {
    python process.py --preflight
    exit $LASTEXITCODE
}

if ($Watch) {
    python batch_watch.py
    exit $LASTEXITCODE
}

if ($Web) {
    python web_app.py
    exit $LASTEXITCODE
}

if ($OnlyPack) {
    if (-not $JobDir) { Write-Host "OnlyPack 需要 -JobDir"; exit 1 }
    python process.py --only-pack --job-dir $JobDir
    exit $LASTEXITCODE
}
if ($OnlyDub) {
    if (-not $JobDir) { Write-Host "OnlyDub 需要 -JobDir"; exit 1 }
    python process.py --only-dub --job-dir $JobDir --force
    exit $LASTEXITCODE
}
if ($OnlyBurn) {
    if (-not $JobDir) { Write-Host "OnlyBurn 需要 -JobDir"; exit 1 }
    python process.py --only-burn --job-dir $JobDir --force
    exit $LASTEXITCODE
}
if ($OnlyShort) {
    if (-not $JobDir) { Write-Host "OnlyShort 需要 -JobDir"; exit 1 }
    python process.py --only-short --job-dir $JobDir --force
    exit $LASTEXITCODE
}

if ($OnlyCopy) {
    if (-not $JobDir) {
        Write-Host "OnlyCopy 需要 -JobDir 指定任务目录"
        exit 1
    }
    $argsList = @("process.py", "--only-copy", "--job-dir", $JobDir)
    if ($Persona)   { $argsList += @("--persona", $Persona) }
    if ($Topic)     { $argsList += @("--topic", $Topic) }
    if ($Preset)    { $argsList += @("--preset", $Preset) }
    python @argsList
    exit $LASTEXITCODE
}

if (-not $Video) {
    Write-Host @"
用法:
  .\run.ps1 -Setup
  .\run.ps1 -Video demo.mp4
  .\run.ps1 -Video demo.mp4 -Persona "资深后端" -Topic "Spring Boot" -Keywords "Java,接口"
  .\run.ps1 -Video demo.mp4 -SkipCut -SkipBurn -OnlyPlatform "bilibili"
  .\run.ps1 -OnlyCopy -JobDir output\xxx -Persona "资深后端"
  .\run.ps1 -Preflight
  .\run.ps1 -Watch
  .\run.ps1 -Web
"@
    exit 1
}

$argsList = @("process.py", $Video)
if ($JobDir)         { $argsList += @("--job-dir", $JobDir) }
if ($SkipCut)        { $argsList += "--skip-cut" }
if ($SkipBurn)       { $argsList += "--skip-burn" }
if ($SkipCopy)       { $argsList += "--skip-copy" }
if ($SkipDub)        { $argsList += "--skip-dub" }
if ($OnlyTranscribe) { $argsList += "--only-transcribe" }
if ($Force)          { $argsList += "--force" }
if ($Preflight)      { $argsList += "--preflight" }
if ($Persona)        { $argsList += @("--persona", $Persona) }
if ($Topic)          { $argsList += @("--topic", $Topic) }
if ($Style)          { $argsList += @("--style", $Style) }
if ($Tone)           { $argsList += @("--tone", $Tone) }
if ($Keywords)       { $argsList += @("--keywords", $Keywords) }
if ($Forbidden)      { $argsList += @("--forbidden", $Forbidden) }
if ($Platforms)      { $argsList += @("--platforms", $Platforms) }
if ($OnlyPlatform)   { $argsList += @("--only-platform", $OnlyPlatform) }
if ($HookStyle)      { $argsList += @("--hook-style", $HookStyle) }
if ($Preset)         { $argsList += @("--preset", $Preset) }

python @argsList
