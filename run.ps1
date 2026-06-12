# 一键处理录屏视频
# 用法: .\run.ps1 -Video "D:\recordings\demo.mp4"

param(
    [Parameter(Mandatory = $true)]
    [string]$Video,

    [switch]$SkipCut,
    [switch]$SkipBurn,
    [switch]$SkipCopy,
    [switch]$Setup
)

$Root = $PSScriptRoot
Set-Location $Root

if ($Setup) {
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pip install auto-editor
    if (-not (Test-Path "config.yaml")) {
        Copy-Item "config.example.yaml" "config.yaml"
        Write-Host "已创建 config.yaml，请按需修改后重试。"
    }
    Write-Host "环境安装完成。另请自行安装 FFmpeg 并加入 PATH。"
    exit 0
}

if (-not (Test-Path ".venv")) {
    Write-Host "请先运行: .\run.ps1 -Setup"
    exit 1
}

.\.venv\Scripts\Activate.ps1

$argsList = @("process.py", $Video)
if ($SkipCut) { $argsList += "--skip-cut" }
if ($SkipBurn) { $argsList += "--skip-burn" }
if ($SkipCopy) { $argsList += "--skip-copy" }

python @argsList
