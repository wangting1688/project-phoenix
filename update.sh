#!/usr/bin/env bash
# =============================================================================
# Project Phoenix 一键更新脚本
#
# 用途: 在部署目录执行 git pull 同步代码, 并按变更内容自动:
#        1) 后端(backend/)变更 -> 重启 systemd 服务(默认 phoenix)
#        2) 前端源码(frontend/src 等)变更 -> npm install + vite build
#        3) 站点健康检查
#
# 用法:
#   bash update.sh                        # 使用默认目录 /www/phoenix
#   UPDATE_DIR=/path/to/app bash update.sh
#   UPDATE_DIR=/path UPDATE_SERVICE=myapi bash update.sh
#
# 注意:
#   - 仅做 fast-forward 拉取, 不会覆盖本地未提交改动(有冲突会报错退出)
#   - 服务器到 GitHub 的 SSH 偶发抖动, 脚本内置 5 次重试
#   - 前端构建需要 node(服务器已装 v24), 首次会 npm install(稍慢)
# =============================================================================
set -uo pipefail

DEPLOY_DIR="${UPDATE_DIR:-/www/phoenix}"
SERVICE="${UPDATE_SERVICE:-phoenix}"
FRONTEND_DIR="$DEPLOY_DIR/frontend"
PULL_LOG="/tmp/phoenix_update_pull.log"

cd "$DEPLOY_DIR" || { echo "!! 无法进入部署目录 $DEPLOY_DIR"; exit 1; }
echo "==> 部署目录: $DEPLOY_DIR"

# ---------- 1) git pull (ff-only, 网络抖动重试) ----------
echo "==> [1/4] git pull --ff-only (服务器到 GitHub 偶发抖动, 内置重试)"
BEFORE=$(git rev-parse HEAD)
OK=0
for i in 1 2 3 4 5; do
  if git pull --ff-only > "$PULL_LOG" 2>&1; then
    cat "$PULL_LOG"
    OK=1
    break
  fi
  cat "$PULL_LOG"
  echo "   pull 失败 (第 $i 次), 5s 后重试..."
  sleep 5
done
if [ "$OK" -ne 1 ]; then
  echo "!! git pull 失败, 请检查服务器到 GitHub 的网络 / Deploy Key"
  exit 1
fi

AFTER=$(git rev-parse HEAD)
if [ "$BEFORE" = "$AFTER" ]; then
  echo "==> 已是最新 (无代码变更)"
  echo "==> [4/4] 健康检查"
  curl -s -o /dev/null -w "site=%{http_code}\n" https://shipin.sdzunyue.wang/ || true
  exit 0
fi

CHANGED=$(git diff --name-only "$BEFORE" "$AFTER")
echo "==> 本次更新文件:"
echo "$CHANGED" | sed 's/^/    /'

# ---------- 2) 前端源码变更 -> build ----------
if echo "$CHANGED" | grep -qE "^(frontend/src/|frontend/public/|frontend/index.html|frontend/vite.config|frontend/package.json|frontend/tsconfig)"; then
  echo "==> [2/4] 前端源码变更, 构建 dist ..."
  cd "$FRONTEND_DIR" || { echo "!! 无法进入前端目录"; exit 1; }
  if [ ! -d node_modules ]; then
    npm install || { echo "!! npm install 失败"; exit 1; }
  fi
  npx vite build 2>&1 | tail -15 || { echo "!! 前端构建失败, 请检查 frontend 依赖/配置"; exit 1; }
  cd "$DEPLOY_DIR"
else
  echo "==> [2/4] 前端无源码变更, 跳过 build"
fi

# ---------- 3) 后端变更 -> 重启服务 ----------
if echo "$CHANGED" | grep -qE "^backend/"; then
  echo "==> [3/4] 后端变更, 重启 $SERVICE ..."
  if systemctl list-unit-files 2>/dev/null | grep -q "^$SERVICE\.service"; then
    systemctl restart "$SERVICE"
    sleep 4
    if systemctl is-active "$SERVICE" >/dev/null 2>&1; then
      echo "   $SERVICE 已重启, 状态 active"
    else
      echo "!! $SERVICE 重启后非 active, 请查看: journalctl -u $SERVICE -n 50"
      exit 1
    fi
  else
    echo "   (未找到 $SERVICE systemd 服务, 请手动重启后端进程)"
  fi
else
  echo "==> [3/4] 后端无变更, 跳过重启"
fi

# ---------- 4) 健康检查 ----------
echo "==> [4/4] 健康检查"
curl -s -o /dev/null -w "site=%{http_code}\n" https://shipin.sdzunyue.wang/ || true
echo "==> 更新完成"
