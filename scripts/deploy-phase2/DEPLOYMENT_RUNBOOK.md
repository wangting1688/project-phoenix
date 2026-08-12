# Phase 2 生产部署执行手册

> 版本：Phase 2 稳定性升级
> 预计维护窗口：30 分钟
> 回滚时间：< 5 分钟
> 影响范围：后端服务（短暂中断），前端无感知

---

## 部署前检查（T-10 分钟）

- [ ] 通知团队成员维护窗口
- [ ] 确认有服务器 SSH 权限
- [ ] 本地执行 `00-preflight-check.sh` 全部通过
- [ ] 数据库有至少 100MB 可用空间
- [ ] 磁盘剩余 > 1GB

---

## 第一步：服务器备份（T-0）

### 1.1 代码备份

```bash
cd /www/phoenix
git status
# 如果有 git，创建备份分支
git branch backup-before-phase2

# 无论如何，tar 全量备份
tar czf /tmp/phoenix_backup_$(date +%Y%m%d_%H%M).tar.gz \
  --exclude='storage' \
  --exclude='*.log' \
  --exclude='__pycache__' \
  --exclude='.venv' \
  .
```

### 1.2 数据库备份

```bash
cd /www/phoenix/backend
# SQLite
cp phoenix.db phoenix.db.before_phase2
cp phoenix.db-shm phoenix.db-shm.before_phase2 2>/dev/null || true
cp phoenix.db-wal phoenix.db-wal.before_phase2 2>/dev/null || true

# 验证备份文件大小
ls -lh phoenix.db.before_phase2
```

### 1.3 Storage 备份（可选，体积大）

```bash
cd /www/phoenix/backend
du -sh storage
# 如果 < 1GB 就备份
tar czf /tmp/storage_backup_$(date +%Y%m%d).tar.gz storage/
```

---

## 第二步：上传代码

使用现有的 `scripts/deploy.sh`（已有完整的发布-备份-清理机制）：

```bash
# 本地执行
cd Project-Phoenix
./scripts/deploy.sh backend
```

> 说明：deploy.sh 会自动：
> - 备份线上后端代码到 `.releases/`
> - 上传新代码（排除 venv/.env/db/storage）
> - 清理线上残留的死代码文件
> - 安装依赖
> - 数据库迁移前自动备份数据库
> - 执行 alembic upgrade head
> - 重启服务
> - 冒烟验证

---

## 第三步：数据库迁移验证

部署脚本已自动执行迁移。部署后手动确认：

```bash
cd /www/phoenix/backend
sudo -u phoenix .venv/bin/alembic current

# 期望输出: ad45eb8a1888 (head)
```

如果不是 head，立即检查：

```bash
sudo -u phoenix .venv/bin/alembic history --verbose
```

---

## 第四步：systemd 配置更新

> 线上已有 phoenix.service，但 Phase 2 提供了增强版（安全加固 + 日志配置）。
> 可选升级，不升级不影响功能。

### 4.1 安装增强版 systemd unit（可选）

```bash
cd /www/phoenix/backend

# 备份原 service
cp /etc/systemd/system/phoenix.service /etc/systemd/system/phoenix.service.bak

# 安装新 service（需要调整路径和用户）
cp deploy/phoenix-backend.service /etc/systemd/system/phoenix.service
# 编辑：修改 WorkingDirectory、User、Group、路径等
vim /etc/systemd/system/phoenix.service

# 安装日志配置
cp deploy/logging.json /www/phoenix/backend/deploy/logging.json
mkdir -p /www/phoenix/backend/logs
chown phoenix:phoenix /www/phoenix/backend/logs

# 重载并重启
systemctl daemon-reload
systemctl restart phoenix
systemctl status phoenix
```

---

## 第五步：冒烟测试

```bash
# 本地执行冒烟测试
cd Project-Phoenix
ADMIN_TOKEN=<你的admin_token> \
  bash scripts/deploy-phase2/02-smoke-test.sh https://你的域名
```

**必须通过的检查项：**

- [ ] `/health` 返回 healthy，含 database + storage
- [ ] 首页正常加载
- [ ] 登录接口正常返回（4xx 也说明链路通）
- [ ] 监控 API 需要鉴权（匿名返回 401/403）
- [ ] admin token 可正常访问监控总览

---

## 第六步：清理卡住的 AI 任务

> Phase 2 之前的版本，服务重启不会清理 ai_tasks。
> 生产环境可能有大量卡在 running 状态的历史任务。

```bash
cd /www/phoenix/backend

# 先 dry-run 预览
sudo -u phoenix .venv/bin/python scripts/deploy-phase2/01-cleanup-stuck-ai-tasks.py --dry-run

# 确认无误后执行
sudo -u phoenix .venv/bin/python scripts/deploy-phase2/01-cleanup-stuck-ai-tasks.py --execute
```

---

## 第七步：上线后观察（30 分钟）

### 7.1 服务状态

```bash
systemctl status phoenix
journalctl -u phoenix -f --since "10 minutes ago"
```

### 7.2 错误日志

```bash
tail -f /var/log/phoenix/api.err.log
# 或
tail -f /www/phoenix/backend/logs/error.log
```

### 7.3 监控 API 观察

每隔 5 分钟访问一次：

```
GET /api/v1/admin/monitoring/overview
```

关注：
- AI 任务失败率是否异常升高
- 是否有新的 failed 任务堆积
- 工作流任务是否正常流转

### 7.4 资源使用

```bash
top -p $(pgrep -f phoenix | head -1)
df -h /
free -h
```

---

## 第八步：确认部署完成

- [ ] 服务稳定运行 > 30 分钟
- [ ] 无新增 500 错误
- [ ] 健康检查持续 healthy
- [ ] AI 任务成功率正常
- [ ] 用户反馈无异常

---

# 回滚方案

## 触发回滚的条件

满足以下任一条件立即回滚：

1. 服务无法启动（systemctl status 显示 failed）
2. 健康检查返回 degraded 或 500
3. 冒烟测试有 > 3 项失败
4. 数据库迁移报错
5. 用户反馈核心功能不可用
6. 错误日志有大量异常堆栈

## 回滚步骤

### 快速回滚（代码 + 数据库）

```bash
# 方式一：使用 deploy.sh 的回滚功能（推荐）
./scripts/deploy.sh rollback

# 方式二：手动回滚
cd /www/phoenix/backend

# 1. 停止服务
systemctl stop phoenix

# 2. 恢复数据库
cp phoenix.db.before_phase2 phoenix.db
rm -f phoenix.db-shm phoenix.db-wal

# 3. 恢复代码（从备份）
rm -rf app alembic
cp -a .releases/backup-xxx/app .
cp -a .releases/backup-xxx/alembic .

# 4. 启动服务
systemctl start phoenix

# 5. 验证
sleep 5
curl -s https://你的域名/health | python3 -m json.tool
```

### 数据库单独回滚

如果代码正常，但 migration 有问题：

```bash
cd /www/phoenix/backend

# 回滚 1 个版本
sudo -u phoenix .venv/bin/alembic downgrade -1

# 或回滚到指定版本
sudo -u phoenix .venv/bin/alembic downgrade f1a2b3c4d5e6

# 验证
sudo -u phoenix .venv/bin/alembic current
```

> **注意**：3 个 migration 都是新增列，downgrade 只是删除列，不丢失数据。

---

# 风险清单

## P0 风险（高）

### R1: SECRET_KEY 默认值导致服务无法启动
- **触发条件**：部署后 `DEBUG=false` 且 `SECRET_KEY` 为默认值
- **后果**：服务启动失败，全站不可用
- **预防**：部署前检查 `.env` 中 `SECRET_KEY` 已设置
- **回滚**：修改 `.env` 或临时设置 `DEBUG=true` 启动

### R2: 数据库迁移失败
- **触发条件**：线上表结构与 migration 预期不符
- **后果**：迁移中断，数据库可能处于不一致状态
- **预防**：
  - 部署前备份数据库
  - 先在 staging 环境验证迁移
  - SQLite 确认表名无大小写问题
- **回滚**：恢复数据库备份文件，代码回滚到旧版本

## P1 风险（中）

### R3: 旧版 SQLite 不支持 batch_alter_table
- **触发条件**：SQLAlchemy 版本过低
- **后果**：迁移失败
- **预防**：确认 `requirements.txt` 中 SQLAlchemy 版本 >= 1.4
- **回滚**：升级 SQLAlchemy 后重试

### R4: AI 任务清理导致历史数据"丢失"
- **触发条件**：将长时间 running 的任务标记为 failed
- **后果**：用户看到任务失败，可能困惑
- **预防**：
  - 只清理 > 30 分钟的 running 任务
  - error_message 标注 `phase2-deploy` 便于追踪
  - 在监控 API 中可查看所有失败任务
- **处理**：无需回滚，属于预期行为

### R5: 新 API 端点影响性能
- **触发条件**：监控 API 被频繁调用
- **后果**：数据库查询压力增加
- **预防**：监控 API 仅 admin 可访问，限制调用频率
- **回滚**：无需回滚，可临时移除 monitoring 路由

## P2 风险（低）

### R6: CORS_ORIGINS 默认值为 *
- **触发条件**：生产环境未修改
- **后果**：跨域安全略宽松
- **预防**：部署后修改 `.env` 中的 `CORS_ORIGINS`
- **回滚**：N/A

### R7: 演示素材自动注入影响新用户
- **触发条件**：新用户注册时自动注入 6 个演示素材
- **后果**：占用存储空间（每个用户 ~1.5MB）
- **预防**：可通过 `DEMO_FOOTAGE_ENABLED=false` 关闭
- **回滚**：N/A

---

# 变更类型确认

## ✅ 无破坏性变更

| 类型 | 是否存在 | 说明 |
|------|:--------:|------|
| 删除字段 | ❌ 无 | 3 个 migration 均为新增列 |
| 修改字段类型 | ❌ 无 | 无类型变更 |
| 修改 API 路径 | ❌ 无 | 只新增 monitoring 端点 |
| 修改认证逻辑 | ❌ 无 | 鉴权逻辑未变 |
| 删除 API 端点 | ❌ 无 | 无删除 |
| 修改响应格式 | ⚠️ 扩展 | `/health` 响应字段增加（向下兼容） |
| 新增配置项 | ✅ 有默认值 | 5 个新增配置均有默认值 |
| 新增数据库表 | ❌ 无 | 仅新增列 |

---

# 部署后验证 Checklist

- [ ] `alembic current` 显示 `ad45eb8a1888 (head)`
- [ ] `/health` 返回 `healthy`，含 database 和 storage 检查
- [ ] 管理员可访问 `/api/v1/admin/monitoring/overview`
- [ ] 普通用户无法访问监控 API（返回 403）
- [ ] 用户登录正常
- [ ] 素材列表加载正常
- [ ] 创建项目正常
- [ ] AI 任务能正常提交
- [ ] 视频渲染能正常完成（输出文件存在且非空）
- [ ] 服务重启后，卡住的任务被正确标记
- [ ] 错误日志无新增异常
- [ ] CPU / 内存使用正常
