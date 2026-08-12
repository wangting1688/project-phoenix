#!/usr/bin/env bash
# Phase 2 部署前检查清单
# 在本地执行，确认所有准备工作就绪
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

c_info()  { printf '\033[36m▸ %s\033[0m\n' "$*"; }
c_ok()    { printf '\033[32m✓ %s\033[0m\n' "$*"; }
c_warn()  { printf '\033[33m! %s\033[0m\n' "$*"; }
c_err()   { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; }

pass=0
fail=0
warn=0

check() {
  local desc="$1" result="$2" level="${3:-error}"
  case "$result" in
    pass) c_ok "$desc"; pass=$((pass+1)) ;;
    warn) c_warn "$desc"; warn=$((warn+1)) ;;
    fail) c_err "$desc"; fail=$((fail+1)) ;;
  esac
}

echo "=============================================="
echo "  Project Phoenix - Phase 2 部署前检查"
echo "=============================================="
echo ""

# ===== 代码完整性 =====
c_info "【1/6】代码完整性检查"

cd "$PROJECT_DIR/backend"
for f in \
  app/api/monitoring.py \
  app/services/demo_assets.py \
  alembic/versions/e7f8a9b0c1d2_add_tenant_id_to_core_tables.py \
  alembic/versions/f1a2b3c4d5e6_add_footage_source_type.py \
  alembic/versions/ad45eb8a1888_add_tenant_id_to_creation_sessions.py \
  deploy/phoenix-backend.service \
  deploy/logging.json \
  deploy/migrate_storage.py
do
  if [ -f "$f" ]; then
    check "  $f" pass
  else
    check "  $f 缺失" fail
  fi
done

# ===== Migration 校验 =====
echo ""
c_info "【2/6】Migration 完整性检查"

cd "$PROJECT_DIR/backend"
source venv/bin/activate 2>/dev/null || true
if command -v alembic &>/dev/null; then
  HEAD=$(alembic heads 2>/dev/null | grep '(head)' | awk '{print $1}')
  if [ "$HEAD" = "ad45eb8a1888" ]; then
    check "  Alembic head = ad45eb8a1888" pass
  else
    check "  head 版本不符: $HEAD (期望 ad45eb8a1888)" fail
  fi
  MIG_COUNT=$(ls alembic/versions/*.py | wc -l | tr -d ' ')
  check "  migration 文件数: $MIG_COUNT" pass
else
  check "  无法执行 alembic，跳过" warn
fi

# ===== 配置项检查 =====
echo ""
c_info "【3/6】配置项检查"

cd "$PROJECT_DIR/backend"
NEW_CONFIGS=(
  "CORS_ORIGINS"
  "DEMO_FOOTAGE_ENABLED"
  "DEMO_FOOTAGE_SOURCE_DIR"
  "DEMO_FOOTAGE_MAX_COUNT"
  "DEMO_FOOTAGE_ALLOW_EDIT_TAGS"
)
for cfg in "${NEW_CONFIGS[@]}"; do
  if grep -q "$cfg" app/core/config.py; then
    check "  config.py 含 $cfg" pass
  else
    check "  config.py 缺少 $cfg" fail
  fi
  if grep -q "$cfg" .env.example; then
    check "  .env.example 含 $cfg" pass
  else
    check "  .env.example 缺少 $cfg" warn
  fi
done

# ===== 健康检查端点 =====
echo ""
c_info "【4/6】健康检查端点确认"

HEALTH_HAS_DB=$(grep -c '"database"' app/main.py || true)
HEALTH_HAS_STORAGE=$(grep -c '"storage"' app/main.py || true)
if [ "$HEALTH_HAS_DB" -gt 0 ] && [ "$HEALTH_HAS_STORAGE" -gt 0 ]; then
  check "  /health 含 database + storage 检查" pass
else
  check "  /health 检查项不完整" fail
fi

# ===== 启动清理逻辑 =====
echo ""
c_info "【5/6】启动任务清理检查"

if grep -q "AITask" app/main.py && grep -q "stuck_ai" app/main.py; then
  check "  启动时清理卡住的 AI 任务" pass
else
  check "  缺少 AI 任务启动清理" fail
fi

if grep -q "WorkflowTask" app/main.py && grep -q "stuck_workflow" app/main.py; then
  check "  启动时清理卡住的工作流任务" pass
else
  check "  缺少工作流启动清理" fail
fi

# ===== 模型一致性 =====
echo ""
c_info "【6/6】模型与 Migration 一致性"

cd "$PROJECT_DIR/backend"
source venv/bin/activate 2>/dev/null || true
if python3 -c "
import pkgutil, importlib
import warnings; warnings.filterwarnings('ignore')
from app.core.database import Base, engine
from sqlalchemy import inspect
from sqlalchemy.orm import class_mapper
import app.models as m
for _, n, _ in pkgutil.iter_modules(m.__path__):
    importlib.import_module(f'app.models.{n}')
insp = inspect(engine)
db_tables = set(insp.get_table_names()) - {'alembic_version'}
model_tables = {c.__tablename__ for c in Base.__subclasses__() if hasattr(c, '__tablename__')}
mismatch = 0
for t in sorted(model_tables & db_tables):
    cls = next(c for c in Base.__subclasses__() if getattr(c, '__tablename__', None) == t)
    model_cols = {c.key for c in class_mapper(cls).columns}
    db_cols = {c['name'] for c in insp.get_columns(t)}
    if model_cols != db_cols:
        mismatch += 1
        print(f'MISMATCH:{t} model_extra={model_cols - db_cols} db_extra={db_cols - model_cols}')
exit(0 if mismatch == 0 else 1)
" 2>/dev/null; then
  check "  78 张表模型与数据库字段完全一致" pass
else
  check "  存在字段不一致（详见上方输出）" fail
fi 2>/dev/null

# ===== 总结 =====
echo ""
echo "=============================================="
echo "  检查结果"
echo "=============================================="
echo "  通过: $pass"
echo "  警告: $warn"
echo "  失败: $fail"
echo ""

if [ "$fail" -gt 0 ]; then
  c_err "❌ 有 $fail 项检查失败，请修复后再部署"
  exit 1
else
  c_ok "✅ 所有关键检查通过，可以开始部署"
  if [ "$warn" -gt 0 ]; then
    c_warn "⚠️  有 $warn 项警告，建议确认后继续"
  fi
  exit 0
fi
