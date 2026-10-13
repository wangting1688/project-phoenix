@echo off
chcp 65001 >nul
REM 一键启动本地视频生成服务：ComfyUI + GPU worker(含H3/TTS/口型)
REM 隧道(LipsyncTunnelWatchdog)和各看门狗已注册为登录计划任务，会自愈。
title Phoenix local GPU services

echo [1/2] 启动 ComfyUI (8188) ...
start "ComfyUI" /D "E:\ComfyUI_windows_portable" "E:\ComfyUI_windows_portable\python_embeded\python.exe" -s ComfyUI\main.py --windows-standalone-build

echo [2/2] 启动 GPU worker (18080, 含 /h3 /tts /sync) ...
start "Phoenix GPU Worker" /D "D:\汪挺\project-Phoenix\project-phoenix\backend" "
D:\汪挺\project-Phoenix\project-phoenix\backend\.venv_lipsync\Scripts\python.exe
" gpu_worker.py

echo.
echo 等待服务就绪(约30-60秒)...
timeout /t 30 /nobreak >nul
echo.
echo ComfyUI:  http://127.0.0.1:8188
echo Worker:   http://127.0.0.1:18080/health
echo H3 health http://127.0.0.1:18080/h3/health
pause
