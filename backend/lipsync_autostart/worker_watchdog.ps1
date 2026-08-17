# worker_watchdog.ps1
# 监控并保活本机 GPU 口型 worker（方案B 派发端点）
# 单一实例保护：worker 以「顶层实例」计数（父进程不是另一个 gpu_worker）。
# 注意：gpu_worker 运行时会自带一个子进程（uvicorn / multiprocessing spawn），
# 其命令行同样含 gpu_worker.py。若按全部匹配进程计数会误判为双开，
# 导致反复 kill+重启。故只统计顶层（父进程不是 gpu_worker 的）实例。
$ErrorActionPreference = 'Continue'

$Backend = 'D:\汪挺\project-Phoenix\project-phoenix\backend'
$PyExe   = Join-Path $Backend '.venv_lipsync\Scripts\python.exe'
$Worker  = Join-Path $Backend 'gpu_worker.py'

# 推理引擎（wav2lip / latentsync）。watchdog 用 Start-Process 拉起 worker，
# 显式在本进程环境里设定，确保重启后不会回退到默认引擎。
if (-not $env:LIPSYNC_ENGINE) { $env:LIPSYNC_ENGINE = 'latentsync' }

function Write-Log($msg){
    try {
        $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        $dir = Join-Path ([System.IO.Path]::GetTempPath()) 'lipsync_autostart'
        if (-not (Test-Path $dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
        [System.IO.File]::AppendAllText((Join-Path $dir 'worker_watchdog.log'), ($ts + ' [worker] ' + $msg + [Environment]::NewLine))
    } catch {}
}

Write-Log 'worker watchdog started'

while ($true) {
    $all = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*gpu_worker.py*' })
    # 顶层实例：父进程不是另一个 gpu_worker（排除 worker 自身的子进程）
    $top = @($all | Where-Object { $all.ProcessId -notcontains $_.ParentProcessId })
    $n = $top.Count
    if ($n -eq 0) {
        Write-Log 'worker not running -> starting'
        try {
            $p = Start-Process -FilePath $PyExe -ArgumentList $Worker -WindowStyle Hidden -PassThru
            Write-Log ('started worker pid=' + $p.Id)
        } catch {
            Write-Log ('start failed: ' + $_.Exception.Message)
        }
        Start-Sleep -Seconds 8
    } elseif ($n -gt 1) {
        Write-Log ('TOO MANY top-level workers (' + $n + ') -> killing all to reset single instance')
        $all | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
        Start-Sleep -Seconds 3
    } else {
        try {
            $r = Invoke-WebRequest -Uri 'http://127.0.0.1:18080/health' -TimeoutSec 5 -UseBasicParsing
            if ($r.StatusCode -ne 200) { Write-Log ('health returned ' + $r.StatusCode) }
        } catch {
            Write-Log ('health check failed: ' + $_.Exception.Message)
        }
        Start-Sleep -Seconds 15
    }
}