很好，我们继续。

现在进入真正影响整个系统稳定性的核心部分：

# Project Phoenix

# AI短视频操作系统

# 数据库设计文档（Database Design）

**文件名：03-Database.md**

**版本：V1.0 MVP**

---

# 1. 数据库设计目标

## 1.1 设计原则

数据库设计遵循：

### 原则一：围绕"创作项目"设计

系统核心对象：

不是用户。

不是视频。

而是：

> Content Project（内容创作项目）

一次创作全过程：

```
主题
 ↓
策划
 ↓
文案
 ↓
审核
 ↓
视频
 ↓
发布
 ↓
数据反馈
```

全部属于一个 Project。

---

### 原则二：支持AI持续学习

所有AI行为必须记录：

* 输入；
* 输出；
* 使用模型；
* Prompt版本；
* 评分结果。

未来才能形成：

AI个人内容模型。

---

### 原则三：支持千人主播规模

设计支持：

* 10000+主播；
* 百万级视频记录；
* 高频AI任务。

---

# 2. 数据库技术

数据库：

MySQL 8.0+

字符集：

```
utf8mb4
```

ORM：

SQLAlchemy 2.x

迁移：

Alembic

---

# 3. 核心实体关系图（ER Diagram）

整体关系：

```
User
 |
 |
Team
 |
 |
ContentProject
 |
 ├── Content
 |
 ├── Planning
 |
 ├── Script
 |
 ├── Review
 |
 ├── Video
 |
 ├── Publish
 |
 └── Analytics


User
 |
 └── Memory


Knowledge
 |
 ├── Prompt
 |
 └── Rule
```

---

# 4. Identity领域

---

# 4.1 user 用户表

表名：

`users`

用途：

保存主播账号。

---

字段：

| 字段            | 类型          | 说明   |
| ------------- | ----------- | ---- |
| id            | bigint      | 主键   |
| username      | varchar(50) | 用户名  |
| phone         | varchar(20) | 手机号  |
| password_hash | varchar     | 密码   |
| nickname      | varchar     | 昵称   |
| avatar        | varchar     | 头像   |
| role          | varchar     | 角色   |
| status        | tinyint     | 状态   |
| created_at    | datetime    | 创建时间 |
| updated_at    | datetime    | 更新时间 |

---

角色：

```
admin
manager
anchor
```

---

# 4.2 team 团队表

表名：

`teams`

用途：

支持加盟团队。

字段：

| 字段         | 类型       |
| ---------- | -------- |
| id         | bigint   |
| name       | varchar  |
| owner_id   | bigint   |
| created_at | datetime |

---

# 4.3 team_user

主播团队关系。

表名：

`team_users`

字段：

| 字段      | 类型      |
| ------- | ------- |
| id      | bigint  |
| team_id | bigint  |
| user_id | bigint  |
| role    | varchar |

---

关系：

```
Team 1:N User
```

---

# 5. Content领域

这是核心。

---

# 5.1 content_projects

创作项目表。

表名：

`content_projects`

核心表。

字段：

| 字段              | 类型       | 说明   |
| --------------- | -------- | ---- |
| id              | bigint   | 项目ID |
| user_id         | bigint   | 主播   |
| source_type     | varchar  | 来源   |
| topic           | varchar  | 主题   |
| category        | varchar  | 分类   |
| status          | varchar  | 状态   |
| workflow_status | varchar  | 流程状态 |
| created_at      | datetime |      |
| updated_at      | datetime |      |

---

source_type：

```
recommend

viral_analysis

custom
```

---

status：

```
draft

processing

completed

failed
```

---

# 5.2 contents

内容分析表。

字段：

| 字段         | 类型      |
| ---------- | ------- |
| id         | bigint  |
| project_id | bigint  |
| title      | varchar |
| summary    | text    |
| audience   | varchar |
| emotion    | varchar |
| tags       | json    |
| score      | decimal |

---

保存：

AI内容理解结果。

---

# 6. Creation领域

---

# 6.1 plannings

AI策划表。

字段：

| 字段         | 说明  |
| ---------- | --- |
| id         | ID  |
| project_id | 项目  |
| target     | 目标  |
| style      | 风格  |
| duration   | 时长  |
| scene      | 场景  |
| strategy   | 策略  |

---

例如：

```
目标：

咨询

风格：

故事

场景：

厨房
```

---

# 6.2 scripts

文案表。

字段：

| 字段         | 说明  |
| ---------- | --- |
| id         | ID  |
| project_id | 项目  |
| type       | 类型  |
| content    | 文案  |
| version    | 版本  |
| score      | 评分  |

---

type：

```
story

knowledge

chat
```

---

支持：

一个项目多个文案。

关系：

```
Project 1:N Script
```

---

# 7. Review审核领域

---

# 7.1 reviews

AI审核结果。

字段：

| 字段              | 说明   |
| --------------- | ---- |
| id              | ID   |
| project_id      | 项目   |
| original_score  | 原创度  |
| marketing_score | 广告感  |
| risk_score      | 风险   |
| consult_score   | 咨询价值 |
| result          | 结果   |

---

result:

```
pass

reject

retry
```

---

# 8. Video领域

---

# 8.1 videos

视频表。

字段：

| 字段         | 说明   |
| ---------- | ---- |
| id         | ID   |
| project_id | 项目   |
| url        | 视频地址 |
| cover_url  | 封面   |
| duration   | 时长   |
| resolution | 分辨率  |
| status     | 状态   |

---

status:

```
generating

completed

failed
```

---

# 9. Publish领域

---

# 9.1 publishes

发布记录。

字段：

| 字段           | 说明  |
| ------------ | --- |
| id           | ID  |
| video_id     | 视频  |
| platform     | 平台  |
| publish_url  | 链接  |
| publish_time | 时间  |

---

platform:

```
kuaishou

douyin

wechat_video
```

---

# 10. Analytics领域

---

# 10.1 video_metrics

视频数据。

字段：

| 字段             | 说明   |
| -------------- | ---- |
| id             | ID   |
| video_id       | 视频   |
| views          | 播放   |
| likes          | 点赞   |
| comments       | 评论   |
| shares         | 分享   |
| profile_visits | 主页访问 |
| consultations  | 咨询   |

---

重点：

consultations

这是核心指标。

---

# 11. AI Memory领域

这是未来竞争力。

---

# 11.1 user_memory

主播AI画像。

字段：

| 字段          | 说明  |
| ----------- | --- |
| id          | ID  |
| user_id     | 主播  |
| memory_type | 类型  |
| content     | 内容  |
| weight      | 权重  |

---

例如：

```
喜欢：

家庭故事

权重：

0.85
```

---

# 12. Knowledge领域

---

# 12.1 prompts

AI提示词版本。

字段：

| 字段      | 说明     |
| ------- | ------ |
| id      | ID     |
| name    | 名称     |
| version | 版本     |
| content | Prompt |
| status  | 状态     |

---

例如：

```
script_writer_v3
```

---

# 12.2 knowledge_rules

规则库。

保存：

* 健康内容规则；
* 平台规则；
* 禁用词。

---

# 13. Workflow领域

---

# 13.1 workflow_tasks

AI任务表。

字段：

| 字段         | 说明   |
| ---------- | ---- |
| id         | ID   |
| project_id | 项目   |
| task_type  | 任务类型 |
| status     | 状态   |
| progress   | 进度   |
| result     | 结果   |

---

task_type:

```
planning

script

review

video
```

---

# 14. 索引设计

重点索引：

---

users:

```
phone
```

---

projects:

```
user_id

created_at

status
```

---

videos:

```
project_id

created_at
```

---

analytics:

```
video_id

created_at
```

---

# 15. V1数据库规模预估

按照：

10000主播。

每天：

2条视频。

一年：

约：

730万视频记录。

MySQL可以支持。

---

# 16. 暂不设计的数据

V2以后：

* CRM客户管理；
* 私域聊天记录；
* 自动成交；
* 直播数据；
* 商品管理。

---

# 数据库设计完成状态

版本：

V1.0

状态：

Approved

---

## 下一步

进入：

# 《04-API接口设计文档》

这一章会定义：

* 前端调用哪些接口；
* 请求参数；
* 返回格式；
* 创建视频流程API；
* AI任务查询API；
* 用户接口；
* 内容接口。

完成后：

我们就可以开始让 AI 编程工具生成 FastAPI 后端代码。


