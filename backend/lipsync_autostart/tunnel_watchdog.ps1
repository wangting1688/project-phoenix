# tunnel_watchdog.ps1
# 监控并保活反向 SSH 隧道：本机 --(ssh -R)--> live:18080 --转发--> 本机 worker:18080
# ssh 断开/网络波动 -> 外层循环自动重连。不依赖文件写（规避隐藏子进程写文件失败）。
$ErrorActionPreference = 'Continue'

$Backend = 'D:\汪挺\project-Phoenix\project-phoenix\backend'

function Write-Log($msg){
    try {
        $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        $dir = Join-Path ([System.IO.Path]::GetTempPath()) 'lipsync_autostart'
        if (-not (Test-Path $dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
        [System.IO.File]::AppendAllText((Join-Path $dir 'tunnel_watchdog.log'), "$ts [tunnel] $msg`n")
    } catch {}
}

# 定位 ssh.exe
$ssh = $null
try { $ssh = (Get-Command ssh.exe -ErrorAction Stop).Source } catch {}
if (-not $ssh) {
    $candidate = 'C:\Windows\System32\OpenSSH\ssh.exe'
    if (Test-Path $candidate) { $ssh = $candidate }
}
if (-not $ssh) { Write-Log 'ERROR: ssh.exe not found, tunnel cannot start'; exit 1 }
Write-Log ('using ssh: ' + $ssh)

# 反向隧道参数：把 live 的 127.0.0.1:18080 转发到本机 worker 127.0.0.1:18080
$sshArgs = @(
    '-N',
    '-R', '18080:127.0.0.1:18080',
    '-o', 'ServerAliveInterval=30',
    '-o', 'ServerAliveCountMax=3',
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'UserKnownHostsFile=/dev/null',
    'live'
)

while ($true) {
    $running = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" |
        Where-Object { $_.CommandLine -like '*-R*18080*' }
    if ($running) {
        Start-Sleep -Seconds 15
        continue
    }
    Write-Log 'tunnel not running -> connecting'
    try {
        $proc = Start-Process -FilePath $ssh -ArgumentList $sshArgs -WindowStyle Hidden -PassThru
        $proc.WaitForExit()
        Write-Log ('ssh exited code=' + $proc.ExitCode + ', reconnect in 5s')
    } catch {
        Write-Log ('ssh launch error: ' + $_.Exception.Message)
    }
    Start-Sleep -Seconds 5
}
