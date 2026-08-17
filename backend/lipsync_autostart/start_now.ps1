# start_now.ps1
# 立即在当前会话拉起两个看门狗（不等下次登录）。开机自启由任务计划程序负责。
$AutoDir = 'D:\汪挺\project-Phoenix\project-phoenix\backend\lipsync_autostart'
$w = Join-Path $AutoDir 'worker_watchdog.ps1'
$t = Join-Path $AutoDir 'tunnel_watchdog.ps1'
Start-Process -FilePath 'powershell.exe' -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"" + $w + "`"") -WindowStyle Hidden
Start-Process -FilePath 'powershell.exe' -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"" + $t + "`"") -WindowStyle Hidden
Write-Host 'lipsync watchdogs launched. logs under lipsync_autostart\logs'
