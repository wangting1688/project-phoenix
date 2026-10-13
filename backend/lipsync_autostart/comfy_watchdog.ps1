$ErrorActionPreference = "Continue"
$root="E:\ComfyUI_windows_portable"
$py=Join-Path $root "python_embeded\python.exe"
$main=Join-Path $root "ComfyUI\main.py"
$log="D:\汪挺\project-Phoenix\project-phoenix\backend\lipsync_autostart\logs"
if(-not(Test-Path $log)){New-Item -ItemType Directory -Path $log -Force|Out-Null}
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
function Up(){try{$r=Invoke-WebRequest "http://127.0.0.1:8188/system_stats" -TimeoutSec 6 -UseBasicParsing;return $r.StatusCode -eq 200}catch{return $false}}
while($true){
 if(Up){Start-Sleep 20;continue}
 $out=Join-Path $log "comfy_out.log"
 $err=Join-Path $log "comfy_err.log"
 Start-Process -FilePath $py -ArgumentList @("-s",$main,"--windows-standalone-build") -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
 Start-Sleep 60
}
