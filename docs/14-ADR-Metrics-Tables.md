# ADR-01 · 效果数据双表并存归档

- 状态：Accepted
- 日期：2026-07-18
- 相关代码：`backend/app/models/tracking.py`、`backend/app/models/video_performance.py`

## 背景

历史上项目里存在两张"效果指标"表：

| 表 | 定义位置 | 主外键 | 字段范围 |
| --- | --- | --- | --- |
| `content_metrics` | `models/tracking.py::ContentMetrics` | `video_id → videos.id` | views / likes / comments / favorites / private_messages / orders |
| `video_publish_records` | `models/video_performance.py::VideoPublishRecord` | `video_id → video_master_content.id`（+ `platform`） | 流量 / 互动 / 完播 / 留存 / 转化 / GMV / 时间戳 …… 共 20+ 列 |

`ContentMetrics` 是早期原型阶段的粗粒度指标表；后来因为要区分平台维度、承载完播/留存/转化等更细指标，实现了 `VideoPublishRecord`。

## 现状扫描（2026-07-18）

- `VideoPublishRecord`：`ingest_service` / `experiment_service` / `audience_memory_service` / `growth_quality_agent_v2` 都在写和读，是**当前唯一在跑的效果表**。
- `ContentMetrics`：全项目 `services/` `api/` 目录下 **0 处引用**，仅剩 model 定义和迁移里的建表 SQL。

## 决策

- **并存但角色明确**：
  - `VideoPublishRecord` = **唯一正式效果表**，所有新代码、新采集只写这张。
  - `ContentMetrics` = **归档遗留**，不删表、不删 model，避免破坏历史迁移与 SQLite 本地 DB 兼容。
- **禁止在新代码里再引用 `ContentMetrics`**（含读写、join、报表）。
- **禁止再往 `ContentMetrics` 里加列或改 schema**。

## 未来清理路径（非当前范围）

若某次大版本决定彻底下线：

1. `alembic` 新建 revision，`drop_table('content_metrics')` 并给出回滚 SQL。
2. 同 revision 删掉 `ContentMetrics` model 类。
3. 生产库执行前先备份，且确认 BI/报表侧无外链依赖。

在没有明确清理动因前，保留现状即可，成本 = 一张空表。

## 参考

- 数据模型速查：本 repo `AGENTS.md` 交接总结小节
- 采集写入路径：`backend/app/services/ingest_service.py`
