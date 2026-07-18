# 阶段五 · 数据采集层方案

**版本**：V1.0（规划）
**产出日期**：2026-07-18
**依据**：MVP Roadmap 阶段五 + 批次 4 冒烟报告；已实现的 `growth_*` 分析层
**决策摘要**：数据源 `d`（手工 + 插件，官方 API 长期目标） · 首批字段 `b`（视频维度 5 项 + 评论 Top10 + 私信量） · 频率 `a`（日粒度） · 对接方式 `a`（直接写现有 `video_publish_records`）

---

## 1. 目标

让 `growth_*` 分析层（因果图 / 归因 / 复盘 / 决策记忆 / 实验 / 学习守护）拥有**真实**的输入数据，从今天的"分析层完备、采集层空缺"过渡到**采集 → 分析 → 反馈**的完整闭环。

**衡量标准（Definition of Done）**：
1. 任一主播可以在系统内为**一条视频**登记发布信息、并上传/同步一次日快照数据。
2. 系统能基于登记数据算出 `PlatformPerformanceScore`，`growth-review/generate-report` 能生成非 mock 的复盘。
3. 至少覆盖抖音 + 小红书两个平台。

---

## 2. 数据流总览

```
[主播端]                        [Phoenix 后端]                     [现有分析层]
─────────────────────────────  ─────────────────────────────  ────────────────
① 手工上传 CSV / 截图 OCR ─┐
② 浏览器插件推送 JSON ─────┼─▶  /api/v1/ingest/*  ──▶  video_publish_records
③ 官方 API 抓取（后期）───┘         │                     │
                                    ▼                     ▼
                             DailyIngestSnapshot     growth_scientist_agent
                             （审计与幂等）           growth_attribution_service
                                                    audience_memory_service
```

**关键决策**：
- 所有渠道的数据统一走 `POST /api/v1/ingest/*` 一组接口，让上游变化不影响下游。
- 存储层复用已存在的 `video_publish_records`（字段已经完全覆盖首批需求）。
- 新增一张 `daily_ingest_snapshots` 表**只做审计与幂等**（谁在什么时间、通过哪种渠道、上报了什么原始 payload），不承担分析用途。

---

## 3. 三期路线（Q1 = d 展开）

**第一期 · 手工上传（1 周内可落地）**
- 主播在网页 `我的作品/绑定平台` 页面：
  - 登记视频：`video_master_id + platform + publish_url + publish_time`
  - 每天在结果页手动填 5 项核心指标（对应 `daily_ingest_snapshots.mode=manual`）
- 优点：零合规风险、零外部依赖，立刻可产生真实数据。
- 缺点：主播容易忘、脏数据多；需要在 UI 上做"必填校验 + 一键截图 OCR"减负。

**第二期 · 浏览器插件（3~4 周）**
- Chrome / Edge 扩展登录主播的抖音创作者中心 / 小红书博主中心：
  - 定时抓取"作品数据"页 DOM，拆出核心字段
  - 通过 `POST /api/v1/ingest/browser` 推送到后端
  - 每次推送带一个 `browser_client_id`（安装态识别），后端做幂等去重
- 优点：数据真实、时效性强、门槛低。
- 缺点：**平台合规风险**，需要在扩展 UI 中显著提示"仅采集你本人账号的公开数据、仅上传到你自己的 Phoenix 实例"；抖音条款近年趋严，需要法务把关。

**第三期 · 官方 API（长期，视商业化推进）**
- 抖音开放平台：主播需要企业号 + 主播主动授权 → `snssdk / open.douyin.com`。
- 小红书商业版：需要合作洽谈。
- 由 `growth_attribution_service` 侧新增 `ingest_official_api` 定时任务拉取。
- 采集层完全屏蔽了下游细节，切换渠道不影响分析层。

---

## 4. 首批采集字段（Q2 = b）

**视频维度（5 项，必填）**
| 字段 | 目标列 | 说明 |
|------|-------|------|
| 播放量 | `video_publish_records.views` | 24h 累计 |
| 点赞 | `.likes` | |
| 评论 | `.comments` | |
| 收藏 | `.favorites` | |
| 分享 | `.shares` | |

**咨询归因（2 项，用于分析层核心）**
| 字段 | 目标列 | 说明 |
|------|-------|------|
| 评论 Top10 | 落 `daily_ingest_snapshots.raw_payload.top_comments` | 供 `audience_memory_service._extract_pain_points` 使用 |
| 私信数 | `.private_message_count` | 咨询漏斗第一层 |

**衍生字段（如果渠道能给就一起收）**
- `completion_rate / first_3_second_retention / avg_watch_time`（插件能取到时全部写入）
- `follows`（涨粉）
- `exposures / reach`（抖音提供）

**明确不采集**：`gmv / order_count / conversion_rate` 这一层依赖打通交易系统，放到第四期之后再谈。

---

## 5. 采集频率（Q3 = a · 日粒度）

- 每条 `video_publish_records` 对应一条最新累计值。
- 每日 00:30 触发的定时任务：为每个已发布视频写入一条 `daily_ingest_snapshots`（增量）。
- `video_publish_records.views` 等字段以最新一次为准（累计值），历史演变通过 `daily_ingest_snapshots` 追溯。
- 未来要看小时粒度或热度衰减曲线时，只要给 `daily_ingest_snapshots` 加一个 `snapshot_hour` 字段即可无痛升级。

---

## 6. 存储与对接（Q4 = a · 复用已有 schema）

**不新增业务表**，只加一张审计表：

```python
# app/models/ingest.py（新增）
class DailyIngestSnapshot(Base, BaseModel):
    __tablename__ = "daily_ingest_snapshots"

    publish_record_id = Column(Integer, ForeignKey("video_publish_records.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    platform = Column(String(50), index=True)
    snapshot_date = Column(String(10), index=True)  # YYYY-MM-DD

    source_mode = Column(String(20), index=True)  # manual / browser / official_api
    source_client = Column(String(100), nullable=True)  # 插件版本 / 上传者标识

    # 落库核心指标（冗余一份，便于分析层直接查询增量）
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    favorites = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    private_message_count = Column(Integer, default=0)

    # 完整原始 payload，供后期回放/审计
    raw_payload = Column(JSON, nullable=True)
```

对 `video_publish_records` 的写入策略：
- 有则 upsert 累计字段（最新值覆盖旧值）
- 无则新建（第一次登记视频时同时创建 publish_record）

---

## 7. 接口设计

**新增路由 `app/api/ingest.py`（前缀 `/api/v1/ingest`）**

- `POST /ingest/videos`：登记一条视频到某平台（等价于建 `VideoMasterContent + VideoPublishRecord`）
- `POST /ingest/daily`：上报一次日快照
  - `mode=manual` 时：`user_id` 从 token 取；`payload` 里必填 5 核心 + 可选私信/评论
  - `mode=browser` 时：`browser_client_id` 必填；`payload` 支持 `top_comments`
- `GET /ingest/videos/{id}/snapshots?limit=30`：查询一条视频的历史快照，供前端展示折线图
- `POST /ingest/browser/handshake`：插件安装握手，返回 `client_secret`（仅一次），后续推送用 `HMAC-SHA256(client_secret, body)` 签名

**幂等策略**
- 唯一键：`(publish_record_id, snapshot_date, source_mode)`
- 同一天同一渠道重复上报 → update 而不是 insert
- 避免主播反复手工填导致重复行

**安全**
- 手工上传通过登录态 JWT 保护
- 浏览器插件走独立的 `browser_client_id + HMAC` 通道，不复用用户 JWT，方便未来 revoke

---

## 8. 落地步骤（可执行的小迭代）

**Iteration-1（后端骨架，2~3 天）**
1. 新增 `DailyIngestSnapshot` model + alembic 迁移
2. 新增 `app/services/ingest_service.py`：`register_video / record_daily_snapshot / list_snapshots`
3. 新增 `app/api/ingest.py` 三个接口 + 幂等测试
4. 完成 `POST /ingest/videos` + `POST /ingest/daily(mode=manual)` 全链路 curl 冒烟

**Iteration-2（前端手工上传，1 周）**
1. `frontend/src/views/works/`：一条视频卡片新增"登记发布"按钮
2. `frontend/src/views/dataEntry/`（新页面）：日快照录入表单，5 核心必填 + 私信/评论可选
3. 结果页展示"最近 7 日折线图"
4. 一键"截图 OCR 填表"（放到 Iteration-2.5，非必需）

**Iteration-3（分析层对接，2 天）**
1. `growth-review/generate-report` 从 `daily_ingest_snapshots` 读增量、`video_publish_records` 读累计
2. `audience_memory_service` 消费 `raw_payload.top_comments`
3. `experiment_service` 用 `video_publish_records.views` 计算实验组差异

**Iteration-4（浏览器插件 MVP，3 周）**
1. 独立仓库 `phoenix-browser-extension`
2. 支持抖音创作者中心一个页面的 DOM 抽取
3. Handshake + HMAC 签名上报
4. 灰度给 3~5 位主播试用

**Iteration-5（官方 API 打通，视商业化节奏）**
- 抖音开放平台 OAuth 主播授权 + 定时拉数据
- 抛弃对浏览器插件的强依赖，但保留作为兜底

---

## 9. 合规与风险

| 风险 | 影响 | 对策 |
|------|------|------|
| 浏览器插件被平台判定为异常抓取 | 主播账号被限流 | 只在主播主动打开创作者中心时抓；控制频率；显著提示"仅本人账号" |
| 手工上传数据造假 | 分析结果失真 | Iteration-2 之后加"数据合理性校验"：单日播放增量不能超过总量、5 项字段相互约束 |
| `daily_ingest_snapshots` 无限增长 | 存储成本、查询慢 | 90 天以上快照转 cold table；累计值以 `video_publish_records` 为准 |
| 平台字段命名/结构变更 | 插件失效 | 每次抓取记录版本号（`source_client=chrome-ext@1.2.3`），后台可按版本回滚解析 |
| GDPR / 主播数据主权 | 法务风险 | 采集内容仅限主播本人账号 + 主播自己创作的内容；提供"一键清除我的所有数据"接口 |

---

## 10. 已知遗留 / 与本方案相关的债务

- **发现-08 · SessionLocal 并发写锁**（冒烟报告）：本方案 `ingest_service` 会被前端和插件高频调用，务必先治理 session 使用，避免 SQLite 在 Iteration-2 阶段就崩。
- **`experiment_service` 里的 `VideoPublishRecord.video_master_id`**：model 里字段名是 `video_id`，服务里用 `video_master_id`，属于历史遗留 bug。数据真实接入后会立刻暴露。计入下一批"服务层字段一致性"专项。
- **`ContentMetrics` 表**：目前采集不写入，建议后期做归档 / 删除决策，避免有两套"效果表"造成混淆。

---

## 11. 下一步

- 与开发者对齐 Iteration-1 时间盒 → 直接开工。
- 与产品对齐 Iteration-2 UI 交互原型（登记按钮位置、日快照表单字段）。
- 与法务对齐 Iteration-4 浏览器插件的合规声明模板。
