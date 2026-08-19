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

# 两个 watchdog 都是常驻死循环，只在登录时触发一次。若进程自身退出（2026-08-19
# 事故：tunnel watchdog 8-17 22:35 退出后无人重连，线上配音报 Connection refused），
# 没有任何机制把它拉回来。这里再注册一个每 5 分钟的一次性自检任务兜底。
# 用 schtasks 而非 Register-ScheduledTask：后者在本机对已存在任务改写会 Access denied。
$selfCheck = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""' +
    (Join-Path $AutoDir 'selfcheck_once.ps1') + '""'
schtasks /create /tn PhoenixTunnelSelfCheck /tr $selfCheck /sc minute /mo 5 /f | Out-Null

Write-Host 'tasks registered: LipsyncTunnelWatchdog, LipsyncWorkerWatchdog (AtLogOn) + PhoenixTunnelSelfCheck (5min)'
