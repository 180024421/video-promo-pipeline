# Install video-promo-pipeline as Windows Service via NSSM (if nssm in PATH)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { Write-Error "Run run.ps1 -Setup first"; exit 1 }
$Nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $Nssm) {
  Write-Host "NSSM not found. Registering Scheduled Task instead..."
  $Action = New-ScheduledTaskAction -Execute $Python -Argument "web_app.py" -WorkingDirectory $Root
  $Trigger = New-ScheduledTaskTrigger -AtStartup
  Register-ScheduledTask -TaskName "VideoPromoWeb" -Action $Action -Trigger $Trigger -Description "video-promo-pipeline web"
  Write-Host "Scheduled task VideoPromoWeb registered."
  exit 0
}
& nssm install VideoPromoWeb $Python web_app.py
& nssm set VideoPromoWeb AppDirectory $Root
& nssm set VideoPromoWeb AppStdout (Join-Path $Root "logs\service.log")
& nssm set VideoPromoWeb AppStderr (Join-Path $Root "logs\service.err.log")
Write-Host "Service VideoPromoWeb installed. Run: nssm start VideoPromoWeb"
