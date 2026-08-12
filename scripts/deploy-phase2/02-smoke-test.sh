#!/usr/bin/env bash
# Phase 2 部署后冒烟测试
# 验证核心功能是否正常工作
set -uo pipefail

BASE_URL="${1:-http://localhost:8000}"

c_info()  { printf '\033[36m▸ %s\033[0m\n' "$*"; }
c_ok()    { printf '\033[32m✓ %s\033[0m\n' "$*"; }
c_warn()  { printf '\033[33m! %s\033[0m\n' "$*"; }
c_err()   { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; }

pass=0
fail=0
warn=0

check_http() {
  local desc="$1" method="$2" path="$3" expected_prefix="$4" extra_args="${5:-}"
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' \
    -X "$method" \
    --max-time 10 \
    $extra_args \
    "$BASE_URL$path" 2>/dev/null || echo "000")

  if [[ "$code" == $expected_prefix* ]]; then
    c_ok "$desc ($code)"
    pass=$((pass+1))
  else
    c_err "$desc ($code, 期望 ${expected_prefix}xx)"
    fail=$((fail+1))
  fi
}

check_body() {
  local desc="$1" path="$2" pattern="$3"
  local body
  body=$(curl -s --max-time 10 "$BASE_URL$path" 2>/dev/null)
  if echo "$body" | grep -q "$pattern"; then
    c_ok "$desc"
    pass=$((pass+1))
  else
    c_err "$desc (未找到: $pattern)"
    fail=$((fail+1))
  fi
}

echo "=============================================="
echo "  Phase 2 冒烟测试"
echo "  目标: $BASE_URL"
echo "=============================================="
echo ""

# ===== 1. 健康检查（Phase 2 核心） =====
c_info "【1/5】健康检查端点"

check_http "  GET /health 返回 200" "GET" "/health" "2"

check_body "  status=healthy" "/health" '"status":"healthy"'
check_body "  含 database 检查" "/health" '"database"'
check_body "  含 storage 检查" "/health" '"storage"'
check_body "  database 状态 ok" "/health" '"status":"ok"'

# ===== 2. 根路径 =====
echo ""
c_info "【2/5】基础端点"

check_http "  GET / 返回 200" "GET" "/" "2"
check_body "  版本号存在" "/" '"version"'

# ===== 3. API 基础链路 =====
echo ""
c_info "【3/5】API 链路"

check_http "  登录接口可达" "POST" "/api/v1/auth/login" "4" \
  '-H "Content-Type: application/json" -d "{\"phone\":\"smoke\",\"password\":\"test\"}"'

check_http "  未授权访问监控返回 401" "GET" "/api/v1/admin/monitoring/overview" "40"

# ===== 4. 监控 API（需要 token，可选测试） =====
echo ""
c_info "【4/5】监控 API（需要 admin token）"

if [ -n "${ADMIN_TOKEN:-}" ]; then
  check_http "  监控总览（已授权）" "GET" "/api/v1/admin/monitoring/overview" "2" \
    "-H \"Authorization: Bearer $ADMIN_TOKEN\""
  check_http "  AI 任务监控" "GET" "/api/v1/admin/monitoring/ai-tasks?limit=5" "2" \
    "-H \"Authorization: Bearer $ADMIN_TOKEN\""
  check_http "  工作流监控" "GET" "/api/v1/admin/monitoring/workflow-tasks?limit=5" "2" \
    "-H \"Authorization: Bearer $ADMIN_TOKEN\""
  check_http "  失败任务" "GET" "/api/v1/admin/monitoring/failed-tasks" "2" \
    "-H \"Authorization: Bearer $ADMIN_TOKEN\""
else
  c_warn "  未设置 ADMIN_TOKEN，跳过监控 API 测试"
  warn=$((warn+4))
fi

# ===== 5. 静态资源（验证安全修复仍在） =====
echo ""
c_info "【5/5】安全基线"

check_http "  静态资源无 token 返回 403" "GET" "/storage/footage/test.mp4" "40"

check_body "  响应为 JSON 格式（不是 HTML 错误页）" "/health" '^{.*}$'

# ===== 总结 =====
echo ""
echo "=============================================="
echo "  测试结果"
echo "=============================================="
echo "  通过: $pass"
echo "  警告: $warn"
echo "  失败: $fail"
echo ""

if [ "$fail" -gt 0 ]; then
  c_err "❌ 有 $fail 项失败，请检查部署"
  exit 1
else
  c_ok "✅ 冒烟测试通过"
  if [ "$warn" -gt 0 ]; then
    c_warn "⚠️  有 $warn 项跳过（设置 ADMIN_TOKEN 可完整测试）"
  fi
  exit 0
fi
