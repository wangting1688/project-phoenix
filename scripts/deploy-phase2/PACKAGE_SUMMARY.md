# Phase 2.5 部署工具包说明

## 目录结构

```
scripts/deploy-phase2/
├── 00-preflight-check.sh      # 部署前检查（本地执行，24项验证）
├── 01-cleanup-stuck-ai-tasks.py # AI卡住任务清理（服务器端执行）
├── 02-smoke-test.sh           # 部署后冒烟测试（15项检查）
├── 03-post-deploy-watch.py    # 上线后30分钟持续监控
├── DEPLOYMENT_RUNBOOK.md      # 部署执行手册 + 回滚方案 + 风险清单
└── PACKAGE_SUMMARY.md         # 本文件
```

## 使用顺序

```
1. 00-preflight-check.sh    ← 本地，部署前
       ↓
2. scripts/deploy.sh backend ← 本地执行部署（已有）
       ↓
3. 02-smoke-test.sh          ← 部署后立即验证
       ↓
4. 01-cleanup-stuck-ai-tasks.py --dry-run  ← 服务器端，先预览
       ↓
5. 01-cleanup-stuck-ai-tasks.py --execute  ← 确认后执行
       ↓
6. 03-post-deploy-watch.py   ← 观察30分钟
```

## 快速开始

```bash
# 1. 部署前检查
bash scripts/deploy-phase2/00-preflight-check.sh

# 2. 部署（用现成脚本）
./scripts/deploy.sh backend

# 3. 冒烟测试
ADMIN_TOKEN=<admin_token> \
  bash scripts/deploy-phase2/02-smoke-test.sh https://your-domain.com

# 4. 清理卡住任务（服务器上）
cd /www/phoenix/backend
sudo -u phoenix .venv/bin/python scripts/deploy-phase2/01-cleanup-stuck-ai-tasks.py --dry-run
sudo -u phoenix .venv/bin/python scripts/deploy-phase2/01-cleanup-stuck-ai-tasks.py --execute

# 5. 上线观察
python3 scripts/deploy-phase2/03-post-deploy-watch.py \
  https://your-domain.com <admin_token>
```

## 详细文档

见 `DEPLOYMENT_RUNBOOK.md`，含：
- 完整部署步骤（8 步）
- 数据库迁移验证
- systemd 升级说明
- 回滚方案（3 种方式）
- 风险清单（P0/P1/P2 分级）
- 破坏性变更确认表
- 部署后验证 Checklist
