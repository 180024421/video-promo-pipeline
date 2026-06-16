# 桌面快捷启动：Web 控制台 + 系统托盘提示
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
Write-Host "启动 video-promo Web 控制台 http://127.0.0.1:8766"
if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    & "$Root\run.ps1" -Setup
}
Start-Process "$Root\.venv\Scripts\python.exe" -ArgumentList "web_app.py" -WorkingDirectory $Root
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8766"
