# register_tasks.ps1
# 注册两个 Windows 任务计划：登录时自动拉起看门狗（开机/重启后自愈）
# 运行身份 = 当前用户（SSH key 在用户 home，必须以当前用户运行才能读到）
$AutoDir = 'D:\汪挺\project-Phoenix\project-phoenix\backend\lipsync_autostart'
$pw  = 'powershell.exe'
$argT = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $AutoDir 'tunnel_watchdog.ps1') + '"'
$argW = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $AutoDir 'worker_watchdog.ps1') + '"'

$tActionT = New-ScheduledTaskAction -Execute $pw -Argument $argT
$tActionW = New-ScheduledTaskAction -Execute $pw -Argument $argW
$tTrigger = New-ScheduledTaskTrigger -AtLogOn
# 允许电池供电运行、多实例忽略、失败每1分钟重启最多3次
$tSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName 'LipsyncTunnelWatchdog' -Action $tActionT -Trigger $tTrigger -Settings $tSettings -Force | Out-Null
Register-ScheduledTask -TaskName 'LipsyncWorkerWatchdog' -Action $tActionW -Trigger $tTrigger -Settings $tSettings -Force | Out-Null

Write-Host 'tasks registered: LipsyncTunnelWatchdog, LipsyncWorkerWatchdog (trigger=AtLogOn)'
