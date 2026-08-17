# stop_now.ps1
# 重启口型服务：杀掉 worker 与隧道进程，由看门狗自动重新拉起。
# 注意：只杀 worker/tunnel，不杀看门狗本身（避免误杀调用方/自身）。
# 若要彻底关停，请先运行本脚本，再手动结束两个 watchdog 的 powershell 进程。
$procs = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq 'python.exe' -and $_.CommandLine -like '*gpu_worker.py*') -or
    ($_.Name -eq 'ssh.exe' -and $_.CommandLine -like '*-R*18080*')
}
foreach ($p in $procs) {
    try { Stop-Process -Id $p.ProcessId -Force; Write-Output ('stopped ' + $p.ProcessId + ' ' + $p.Name) } catch { Write-Output ('fail ' + $p.ProcessId) }
}
Write-Output 'restart signal sent (watchdog will relaunch worker/tunnel)'