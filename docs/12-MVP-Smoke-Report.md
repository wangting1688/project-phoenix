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

---

## 五、批次 5 追加轮次（2026-07-18）

自批次 4 冒烟之后陆续推进的多批次改动汇总，均已 push 到 `origin/main`。

### 5.1 交付清单

| 提交 | 类型 | 摘要 |
|------|------|------|
| `88e0d67` | feat | 阶段五 Iter-1 数据采集骨架 |
| `8e5d26a` | feat | 阶段五 Iter-3 分析层对接采集数据 + 修历史脏引用 |
| `f08b580` | fix | growth-review 3 处历史脏引用，`generate-report` 端到端 200 |
| `8fd2014` | feat | 阶段五 Iter-2 手工数据登记页面 |
| `3a3da8b` | fix | 前端 `icons.ts` 缺失导出，`vite build` 通过 |
| `061f199` | fix | 清理 v1 历史脏引用（`growth_quality_agent` + `production_repair_agent`） |
| `98ffab3` | perf | 前端拆 vendor chunk，业务主包 1244 kB → 55 kB |
| `4fae7ed` | docs | ADR-01 归档 `ContentMetrics` vs `VideoPublishRecord` 双表决策 |

### 5.2 验证记录

- **`growth_quality_agent` 单元冒烟**（`plan#4`, 5 段）：`_evaluate_hook=100`、`_calculate_info_density`、`_analyze_emotion_curve`、`_identify_follow_reasons`、`_detect_risks` 全绿，无 `AttributeError`。
- **脏引用静态扫描**：`plan.platform` / `product_name` / `product_category` / `hook_segment.script_content` 未守护引用 = 0。
- **前端构建对比**：
  - Baseline：业务主包 `1244 kB`（gzip `404 kB`），单包超警戒线。
  - Batch A：业务主包 `55 kB`（gzip `21 kB`），`vendor-element-plus 906 kB / vendor-el-icons 171 kB / vendor-vue 110 kB` 分离。
- **`viral-analysis/generate-report`**：`f08b580` 后端到端 200，历史脏引用清零。

### 5.3 数据现状（本地 SQLite）

- `plan#4` 具备 5 段（hook / pain / social_proof / conversion / general），供分析层使用。
- `video_publish_records`：#1 douyin（胶原蛋白测试）、#2 xiaohongshu、#3 Iter-2 空模板。
- `daily_ingest_snapshots`：3 条。
- `video_master_content#1` 已通过 SQL 关联 `edit_plan_id=4`。

### 5.4 遗留 / 未修（记录，非本轮范围）

- **前端主 vendor 天花板**：`vendor-element-plus 906 kB` 仍超 500 kB 警告线，根因是 `main.ts` 里 `app.use(ElementPlus)` + 全量 icons 注册，属结构性重构，待独立批次处理。
- **发现 08（SessionLocal 未统一）**：状态不变，等专项治理。
- **发现 01（ContentProject status/workflow_status 语义）**：未推动，等前后端契约对齐。
