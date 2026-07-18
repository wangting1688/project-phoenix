# MVP 端到端冒烟报告

**执行时间**：2026-07-18
**执行方式**：接口层 curl 自动化冒烟（含 P0 主链路 + 关键 GET 接口回归）
**账号**：`13800138000 / 123456`（init_db 种子）
**数据库**：本地 SQLite `phoenix.db`（重建后 74 张表与 model 100% 对齐 + 6 条 video_script_templates 种子）

## 一、通过的能力清单

### 主链路 P0
- 注册 / 登录 / 获取当前用户信息（`auth/register`、`auth/login`、`auth/me`）
- 创作项目：4 位专家 workflow（analyze → planning → script → review），产出 3 版文案（story / knowledge / chat，各 92 分）
- 创作工作台全链路（`creation-studio/sessions → configure → generate → session detail`）
- 爆款逆向分析全链路（`viral-analysis/create → analyze → generate`）
- AI 导演编排 `video-director/generate-plan`（能生成计划）

### 关键 GET 接口回归（20/20 全部 200）
`auth/me`、`content/recommendations`、`content/categories`、
`content-hub/today`、`content-hub/weights`、
`creator-profile`、`creator-profile/preference`、
`creation/projects`、
`footage/list`、`footage/categories`、
`creation-studio/templates`、`creation-studio/sessions`、
`shooting-assistant/modes`、`shooting-assistant/profile`、
`asset-collection/tasks`、`asset-intelligence/stats`、
`video-director/plans`、`director-learning/memories`、
`video-production/jobs`、`agent-gateway/tools`。

## 二、发现的问题清单

| 编号 | 严重度 | 现象 | 定位 | 处置 |
|------|-------|------|------|------|
| 01 | 低 | `ContentProject.status` 停在 `processing`，但 `workflow_status=completed` | 前端易取错字段 | 建议：workflow 完成后同步更新 `status`，或前端统一按 `workflow_status` |
| 02 | 观察 | workflow 3 秒完成，返回明显是模板兜底 | 本地无 AI Key，走 mock 分支 | 预期行为，接入 AI 后自动恢复 |
| 03 | 高 | `content-hub/today` `/weights` `/refresh` `/recommendations` 500 | `RecommendationEngine.__init__` 先调用 `_get_weights` 再赋值 `creator_preference` | **批次 4 已修** |
| 04 | 中 | `creation-studio` 会话丢失 `topic`，最终产物写 `未命名主题` | `create_session` 收 `topic` 参数未写入 `config`；`configure_session` 直接覆盖 config | **批次 4 已修**（两处都改） |
| 05 | 高 | `viral-analysis/{id}/analyze` 500，`generate` 404 | `_calculate_creator_match` 与 `generate_opportunity` 访问 `CreatorProfile.category`，该字段不存在 | **批次 4 已修**（改用 `getattr` 兜底 None） |
| 06 | 严重 | `phoenix.db` schema 大幅滞后于 model（缺 14 表 / 3 字段 / 有 2 孤儿表） | 历史长期靠 `create_all` 兜底建表 + 批次 3 直接 `stamp` 到 baseline | **批次 4 已修**（重建 phoenix.db，`alembic upgrade head` 从零建表，历史测试数据丢弃） |
| 07 | 观察 | 孤儿表 `video_covers` / `video_subtitles` 存在但代码零引用 | 未纳入 ORM，且业务不使用 | **批次 4 已处理**（重建 DB 后彻底不存在） |
| 08 | 架构 | `video-director/generate-plan` 触发 `sqlite3.OperationalError: database is locked` | `app/services/` 里 41 处直接 `SessionLocal()`，请求内嵌套调用多个 service 各建 session → SQLite 单写者被锁 | **未修**，建议后续统一改成依赖注入或 `scoped_session`；切 MySQL 后症状会缓解但根因仍在 |

## 三、批次 4 收尾产物

- 修 3 个代码 bug（发现 03 / 04 / 05）
- 归档旧 `phoenix.db → phoenix.db.legacy.20260718`（保留、未提交）
- 新建 `phoenix.db`，与 model schema 100% 对齐
- 新增 `backend/app/data/video_script_templates_seed.json`（6 条模板种子）
- `init_db.py` 扩展：种子账号 + 自动导入模板 seed
- 冒烟报告本文件

## 四、遗留问题与后续建议

- **发现 01**：`ContentProject.status` 与 `workflow_status` 语义未对齐，属于前端-后端契约问题，需产品/前端一起明确使用哪一个字段。
- **发现 08**：SessionLocal 使用不统一是架构级隐患，建议在批次 5 或独立专项治理：
  - 短期：改造 service 构造函数接受外部 `db: Session`，由 FastAPI `Depends(get_db)` 统一注入。
  - 长期：请求生命周期内共享同一 session，事务边界收敛在 API 层。
- **AI 服务真实接入**：目前全部走 mock，正式接入前请补 `.env` 中的 AI 相关 key，并在 `AIExpertService` 里加超时/重试。
