# Register batch_watch as scheduled task (run as current user)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Root\run.ps1`" -Watch" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "VideoPromoBatchWatch" -Action $Action -Trigger $Trigger -Description "video-promo-pipeline watch_in monitor"
Write-Host "Scheduled task VideoPromoBatchWatch registered."
