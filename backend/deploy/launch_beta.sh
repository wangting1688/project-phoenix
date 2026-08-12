#!/usr/bin/env bash
# Project Phoenix - 封闭内测一键部署脚本
# 作用: 准备生产级 .env（关闭 DEBUG、随机 SECRET_KEY、限制 CORS），
#       校验配置（触发生产护栏），启动服务并自检 /health。
# 用法: ./launch_beta.sh [前端域名, 默认 http://127.0.0.1:5173]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${ROOT}/.env"
PY="${ROOT}/venv/bin/python3"
[ -x "$PY" ] || PY="$(command -v python3)"
CORS_ARG="${1:-http://127.0.0.1:5173}"

echo "==> [1/5] 准备 .env (${ENV_FILE})"
[ -f "$ENV_FILE" ] || { echo "错误: 找不到 $ENV_FILE"; exit 1; }

set_env() {
  # $1 key  $2 value
  if grep -q "^$1=" "$ENV_FILE"; then
    sed -i.bak -E "s|^$1=.*|$1=$2|" "$ENV_FILE"
  else
    printf '\n%s=%s\n' "$1" "$2" >> "$ENV_FILE"
  fi
}

# 关闭 DEBUG
set_env "DEBUG" "false"
# CORS 限制为具体域名（封闭内测用前端实际地址）
set_env "CORS_ORIGINS" "$CORS_ARG"
# SECRET_KEY: 若为默认值或缺失，则生成强随机值
if ! grep -q "^SECRET_KEY=" "$ENV_FILE" || grep -q "^SECRET_KEY=phoenix-secret-key-change-in-production" "$ENV_FILE"; then
  NEW_KEY="$(openssl rand -hex 32)"
  set_env "SECRET_KEY" "$NEW_KEY"
  echo "    已生成新的随机 SECRET_KEY"
fi

echo "==> [2/5] 校验配置（会触发生产护栏: SECRET_KEY / CORS）"
"$PY" - <<'PY'
import sys
import app.main  # 导入即触发模块级生产护栏
from app.core.config import settings
print(f"    DEBUG={settings.DEBUG}  CORS={settings.CORS_ORIGINS}  DB={settings.DATABASE_URL.split(':')[0]}")
if settings.DEBUG:
    print("错误: DEBUG 必须为 false"); sys.exit(1)
if settings.CORS_ORIGINS.strip() == "*":
    print("错误: CORS_ORIGINS 不能为 *"); sys.exit(1)
print("    配置校验通过（护栏已触发且无异常）")
PY

echo "==> [3/5] 启动服务"
if command -v launchctl >/dev/null 2>&1 && [ -f "${ROOT}/deploy/com.phoenix.backend.plist" ]; then
  cp "${ROOT}/deploy/com.phoenix.backend.plist" "${HOME}/Library/LaunchAgents/"
  launchctl load "${HOME}/Library/LaunchAgents/com.phoenix.backend.plist"
  echo "    已通过 launchd 启动"
else
  nohup "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.beta.log 2>&1 &
  echo "    已后台启动 uvicorn (pid $!)"
fi

echo "==> [4/5] 等待服务就绪"
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "==> [5/5] 自检"
curl -fsS http://127.0.0.1:8000/health && echo
echo "部署完成。前端访问: ${CORS_ARG}  后端: http://127.0.0.1:8000"
