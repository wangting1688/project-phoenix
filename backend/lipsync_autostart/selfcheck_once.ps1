# selfcheck_once.ps1
# 一次性自检（供每 5 分钟的 PhoenixTunnelSelfCheck 定时任务调用，跑完即退出）。
#
# 背景：worker/tunnel 两个 watchdog 是常驻死循环，只在登录时触发一次。
# 2026-08-19 事故：tunnel watchdog 于 8-17 22:35 退出后无人重连，
# 线上后端调本机 TTS 得到 Connection refused，任务报「配音生成失败」。
# 本脚本兜住那种情况：发现 watchdog 不在就重新拉起，不做任何常驻等待。
$ErrorActionPreference = 'Continue'

$AutoDir = 'D:\汪挺\project-Phoenix\project-phoenix\backend\lipsync_autostart'

function Write-Log($msg){
    try {
        $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        $dir = Join-Path ([System.IO.Path]::GetTempPath()) 'lipsync_autostart'
        if (-not (Test-Path $dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
        [System.IO.File]::AppendAllText((Join-Path $dir 'selfcheck.log'), "$ts [selfcheck] $msg`n")
    } catch {}
}

function Test-Watchdog([string]$scriptName){
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
        Where-Object { $_.CommandLine -like "*$scriptName*" -and $_.ProcessId -ne $PID })
    return $procs.Count -gt 0
}

function Start-Watchdog([string]$scriptName){
    $path = Join-Path $AutoDir $scriptName
    $args = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $path + '"'
    try {
        Start-Process -FilePath 'powershell.exe' -ArgumentList $args -WindowStyle Hidden | Out-Null
        Write-Log "started $scriptName"
    } catch {
        Write-Log "start $scriptName failed: $($_.Exception.Message)"
    }
}

foreach ($s in @('tunnel_watchdog.ps1', 'worker_watchdog.ps1')) {
    if (Test-Watchdog $s) { continue }
    Write-Log "$s not running"
    Start-Watchdog $s
}