#!/usr/bin/env bash
#
# Project Phoenix 一键部署脚本
#
#   ./scripts/deploy.sh            # 全量部署 (前端 + 后端)
#   ./scripts/deploy.sh backend    # 只部署后端
#   ./scripts/deploy.sh frontend   # 只部署前端
#   ./scripts/deploy.sh status     # 查看线上状态
#   ./scripts/deploy.sh logs       # 查看线上日志 (跟随)
#   ./scripts/deploy.sh rollback   # 回滚到上一个版本
#
# 说明: 只操作 /www/phoenix 与 phoenix.service, 不触碰服务器上其他站点。
#       线上 .env 与 data/ 数据库永不被覆盖。

set -euo pipefail

# ---------- 配置 ----------
SSH_HOST="root@106.15.66.71"
SSH_KEY="$HOME/.ssh/workbuddy_aliyun_temp"
SITE="https://shipin.sdzunyue.wang"
REMOTE_ROOT="/www/phoenix"
SERVICE="phoenix"
RUN_USER="phoenix"
KEEP_RELEASES=3

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15 -i $SSH_KEY $SSH_HOST"

# 上传时排除的内容: 虚拟环境/缓存/本地密钥/本地数据库/macOS 垃圾文件
EXCLUDES=(
  --exclude 'venv' --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc'
  --exclude '.env' --exclude '*.db' --exclude '*.db-shm' --exclude '*.db-wal'
  --exclude '*.sqlite' --exclude '*.sqlite3' --exclude '*.legacy.*'
  --exclude 'storage' --exclude 'data' --exclude '.pytest_cache'
  --exclude '.DS_Store' --exclude '._*' --exclude 'uvicorn.log' --exclude '*.log'
)

# ---------- 输出 ----------
c_info()  { printf '\033[36m▸ %s\033[0m\n' "$*"; }
c_ok()    { printf '\033[32m✓ %s\033[0m\n' "$*"; }
c_warn()  { printf '\033[33m! %s\033[0m\n' "$*"; }
c_err()   { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; }
die()     { c_err "$*"; exit 1; }

# ---------- 前置检查 ----------
preflight() {
  [ -f "$SSH_KEY" ] || die "找不到 SSH 密钥: $SSH_KEY"
  $SSH 'echo ok' >/dev/null 2>&1 || die "无法连接服务器 $SSH_HOST"
  c_ok "服务器连接正常"
}

# ---------- 备份当前线上版本 ----------
backup_remote() {
  local what="$1"   # backend | frontend
  $SSH "bash -s" <<EOF
set -e
STAMP=\$(date +%Y%m%d-%H%M%S)
BK="$REMOTE_ROOT/.releases/$what-\$STAMP"
mkdir -p "$REMOTE_ROOT/.releases"
if [ "$what" = "backend" ] && [ -d "$REMOTE_ROOT/backend/app" ]; then
  mkdir -p "\$BK"
  cp -a "$REMOTE_ROOT/backend/app" "\$BK/app"
  cp -a "$REMOTE_ROOT/backend/alembic" "\$BK/alembic" 2>/dev/null || true
  cp -a "$REMOTE_ROOT/backend/requirements.txt" "\$BK/" 2>/dev/null || true
  echo "备份: \$BK"
elif [ "$what" = "frontend" ] && [ -d "$REMOTE_ROOT/frontend/dist" ]; then
  mkdir -p "\$BK"
  cp -a "$REMOTE_ROOT/frontend/dist" "\$BK/dist"
  echo "备份: \$BK"
fi
# 只保留最近 N 份
ls -1dt "$REMOTE_ROOT/.releases/$what-"* 2>/dev/null | tail -n +\$(( $KEEP_RELEASES + 1 )) | while read -r old; do
  rm -rf "\$old"; echo "清理旧备份: \$(basename "\$old")"
done
EOF
}

# ---------- 部署后端 ----------
deploy_backend() {
  c_info "备份线上后端..."
  backup_remote backend

  c_info "上传后端代码..."
  ( cd "$PROJECT_DIR/backend" && tar czf - "${EXCLUDES[@]}" . ) 2>/dev/null \
    | $SSH "tar xzf - -C $REMOTE_ROOT/backend" \
    || die "后端上传失败"
  c_ok "后端代码已上传"

  c_info "同步依赖 + 数据库迁移..."
  $SSH "bash -s" <<EOF
set -e
cd $REMOTE_ROOT/backend
chown -R $RUN_USER:$RUN_USER app alembic scripts requirements.txt alembic.ini run.py init_db.py 2>/dev/null || true
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
[ -d .venv ] || python3.11 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
sudo -u $RUN_USER .venv/bin/alembic upgrade head 2>&1 | grep -E 'Running upgrade|ERROR' || echo "  (数据库已是最新)"
EOF
  c_ok "依赖与数据库就绪"

  c_info "重启服务..."
  $SSH "systemctl restart $SERVICE"
  sleep 6
}

# ---------- 部署前端 ----------
deploy_frontend() {
  c_info "本地构建前端..."
  ( cd "$PROJECT_DIR/frontend" && npx vite build ) >/tmp/phoenix-build.log 2>&1 \
    || { tail -25 /tmp/phoenix-build.log; die "前端构建失败 (详见 /tmp/phoenix-build.log)"; }
  [ -f "$PROJECT_DIR/frontend/dist/index.html" ] || die "构建产物缺少 index.html"
  c_ok "前端构建完成"

  c_info "备份线上前端..."
  backup_remote frontend

  c_info "上传前端产物..."
  # 传到临时目录再原子切换, 避免用户访问到半成品
  ( cd "$PROJECT_DIR/frontend/dist" && tar czf - --exclude '.DS_Store' --exclude '._*' . ) 2>/dev/null \
    | $SSH "rm -rf $REMOTE_ROOT/frontend/.dist-new && mkdir -p $REMOTE_ROOT/frontend/.dist-new && tar xzf - -C $REMOTE_ROOT/frontend/.dist-new" \
    || die "前端上传失败"

  $SSH "bash -s" <<EOF
set -e
cd $REMOTE_ROOT/frontend
[ -f .dist-new/index.html ] || { echo "上传产物不完整, 中止切换"; exit 1; }
rm -rf dist.old
[ -d dist ] && mv dist dist.old
mv .dist-new dist
rm -rf dist.old
chown -R $RUN_USER:$RUN_USER dist
EOF
  c_ok "前端已上线"
}

# ---------- 冒烟验证 ----------
verify() {
  c_info "冒烟验证..."
  local fail=0

  local svc
  svc=$($SSH "systemctl is-active $SERVICE" 2>/dev/null || true)
  if [ "$svc" = "active" ]; then c_ok "服务状态: active"
  else c_err "服务未运行 (状态: $svc)"; fail=1; fi

  local api
  api=$($SSH "curl -s -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8110/docs" 2>/dev/null || true)
  if [ "$api" = "200" ]; then c_ok "后端 API: 200"
  else c_err "后端 API 异常: $api"; fail=1; fi

  local web
  web=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$SITE/" 2>/dev/null || true)
  if [ "$web" = "200" ]; then c_ok "站点首页: 200"
  else c_err "站点首页异常: $web"; fail=1; fi

  local login
  login=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST "$SITE/api/v1/auth/login" \
    -H 'Content-Type: application/json' -d '{"phone":"__probe__","password":"__probe__"}' 2>/dev/null || true)
  # 探针账号不存在, 预期 4xx; 只要不是 5xx/000 就说明反代与后端链路通
  case "$login" in
    2*|4*) c_ok "API 反代链路: $login (链路正常)";;
    *)     c_err "API 反代异常: $login"; fail=1;;
  esac

  if [ "$fail" -ne 0 ]; then
    c_warn "验证未全部通过, 最近错误日志:"
    $SSH "tail -20 /var/log/phoenix/api.err.log" 2>/dev/null || true
    return 1
  fi
  return 0
}

# ---------- 回滚 ----------
do_rollback() {
  c_info "可用备份:"
  local avail
  avail=$($SSH "ls -1dt $REMOTE_ROOT/.releases/* 2>/dev/null | head -10 | xargs -r -n1 basename")
  [ -n "$avail" ] || die "没有可用备份 (首次部署后才会生成)"
  echo "$avail" | sed 's/^/  /'
  echo
  read -r -p "输入要回滚的备份名 (直接回车取消): " pick
  [ -n "$pick" ] || { c_warn "已取消"; exit 0; }

  $SSH "bash -s" <<EOF
set -e
BK="$REMOTE_ROOT/.releases/$pick"
[ -d "\$BK" ] || { echo "备份不存在: \$BK"; exit 1; }
case "$pick" in
  backend-*)
    rm -rf $REMOTE_ROOT/backend/app
    cp -a "\$BK/app" $REMOTE_ROOT/backend/app
    [ -d "\$BK/alembic" ] && rm -rf $REMOTE_ROOT/backend/alembic && cp -a "\$BK/alembic" $REMOTE_ROOT/backend/alembic
    [ -f "\$BK/requirements.txt" ] && cp -a "\$BK/requirements.txt" $REMOTE_ROOT/backend/
    chown -R $RUN_USER:$RUN_USER $REMOTE_ROOT/backend/app $REMOTE_ROOT/backend/alembic
    find $REMOTE_ROOT/backend -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    systemctl restart $SERVICE
    echo "后端已回滚 (注意: 数据库迁移不会自动降级)"
    ;;
  frontend-*)
    rm -rf $REMOTE_ROOT/frontend/dist
    cp -a "\$BK/dist" $REMOTE_ROOT/frontend/dist
    chown -R $RUN_USER:$RUN_USER $REMOTE_ROOT/frontend/dist
    echo "前端已回滚"
    ;;
  *) echo "无法识别的备份类型: $pick"; exit 1;;
esac
EOF
  sleep 5
  verify && c_ok "回滚完成"
}

# ---------- 状态 ----------
do_status() {
  $SSH "bash -s" <<EOF
echo "=== 服务 ==="
systemctl is-enabled $SERVICE 2>/dev/null | sed 's/^/开机自启: /'
systemctl is-active  $SERVICE 2>/dev/null | sed 's/^/运行状态: /'
systemctl show -p ActiveEnterTimestamp --value $SERVICE | sed 's/^/启动时间: /'
echo "=== 端口 ==="
ss -tlnp 2>/dev/null | grep 8110 | awk '{print \$4}' | sed 's/^/监听: /' || echo "8110 未监听"
echo "=== 磁盘 ==="
du -sh $REMOTE_ROOT 2>/dev/null | sed 's/^/占用: /'
df -h / | tail -1 | awk '{print "根分区: "\$3" / "\$2" ("\$5")"}'
echo "=== 证书 ==="
openssl x509 -enddate -noout -in /etc/letsencrypt/live/shipin.sdzunyue.wang/fullchain.pem 2>/dev/null | sed 's/notAfter=/到期: /'
echo "=== 备份 ==="
ls -1dt $REMOTE_ROOT/.releases/* 2>/dev/null | head -6 | xargs -r -n1 basename | sed 's/^/  /' | grep . || echo "  (无)"
echo "=== 最近错误 ==="
grep -iE "error|traceback|exception" /var/log/phoenix/api.err.log 2>/dev/null | tail -5 || echo "  (无)"
EOF
  echo "=== 站点 ==="
  printf '首页: %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$SITE/" || echo 000)"
}

# ---------- 主流程 ----------
main() {
  local action="${1:-all}"
  case "$action" in
    status)   preflight; do_status ;;
    logs)     preflight; c_info "跟随日志 (Ctrl-C 退出)"; $SSH "tail -f /var/log/phoenix/api.err.log" ;;
    rollback) preflight; do_rollback ;;
    backend)  preflight; deploy_backend; verify && c_ok "后端部署完成 → $SITE" ;;
    frontend) preflight; deploy_frontend; verify && c_ok "前端部署完成 → $SITE" ;;
    all)      preflight; deploy_frontend; deploy_backend; verify && c_ok "全量部署完成 → $SITE" ;;
    -h|--help|help)
      sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
    *) die "未知参数: $action (可用: all | backend | frontend | status | logs | rollback)" ;;
  esac
}

main "$@"
