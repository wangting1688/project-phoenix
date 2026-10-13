$AutoDir = "D:\汪挺\project-Phoenix\project-phoenix\backend\lipsync_autostart"
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$AutoDir\comfy_watchdog.ps1`""
$action = New-ScheduledTaskAction -Execute powershell.exe -Argument $arg
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "ComfyUIWatchdog" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Output "REGISTERED"
