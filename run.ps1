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
    [switch]$OnlyTranscribe,
    [switch]$OnlyCopy,
    [switch]$Force,
    [switch]$Preflight,
    [switch]$Setup,
    [switch]$Watch,
    [switch]$Web
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

if ($OnlyCopy) {
    if (-not $JobDir) {
        Write-Host "OnlyCopy 需要 -JobDir 指定任务目录"
        exit 1
    }
    python process.py --only-copy --job-dir $JobDir
    exit $LASTEXITCODE
}

if (-not $Video) {
    Write-Host @"
用法:
  .\run.ps1 -Setup
  .\run.ps1 -Video demo.mp4
  .\run.ps1 -Video demo.mp4 -SkipCut -SkipBurn
  .\run.ps1 -Video demo.mp4 -OnlyTranscribe
  .\run.ps1 -OnlyCopy -JobDir output\xxx
  .\run.ps1 -Preflight
  .\run.ps1 -Watch
  .\run.ps1 -Web
"@
    exit 1
}

$argsList = @("process.py", $Video)
if ($JobDir) { $argsList += @("--job-dir", $JobDir) }
if ($SkipCut) { $argsList += "--skip-cut" }
if ($SkipBurn) { $argsList += "--skip-burn" }
if ($SkipCopy) { $argsList += "--skip-copy" }
if ($OnlyTranscribe) { $argsList += "--only-transcribe" }
if ($Force) { $argsList += "--force" }
if ($Preflight) { $argsList += "--preflight" }

python @argsList
