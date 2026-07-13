# Project Phoenix

# AI短视频操作系统

# 系统架构设计文档（Architecture Design）

**文件名：02-Architecture.md**

**版本：V1.0 MVP**

---

# 1. 架构设计目标

## 1.1 核心目标

建立一个：

> AI Native（AI原生）的短视频内容生产平台。

系统不是传统管理软件，而是：

> 多个AI专家协同完成内容生产任务的平台。

---

# 2. 总体架构

系统采用：

## 五层架构

```text
┌─────────────────────────────┐
│          Web Layer           │
│ Vue3 + TypeScript            │
│ PC + Mobile Responsive       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│        API Layer             │
│ FastAPI                      │
│ Authentication               │
│ REST API                     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│     AI Workflow Layer        │
│ LangGraph / Workflow Engine  │
│                              │
│ Content → Script → Video     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│      AI Expert Layer         │
│                              │
│ 内容专家                     │
│ 策划专家                     │
│ 文案专家                     │
│ 审核专家                     │
│ 视频专家                     │
│ 运营专家                     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Infrastructure Layer         │
│ MySQL                        │
│ Redis                        │
│ OSS                          │
│ FFmpeg                       │
│ AI Provider                  │
└─────────────────────────────┘
```

---

# 3. 技术选型

## 3.1 前端技术

| 项目   | 技术           |
| ---- | ------------ |
| 框架   | Vue3         |
| 语言   | TypeScript   |
| 构建工具 | Vite         |
| UI组件 | Element Plus |
| 移动组件 | Vant         |
| 状态管理 | Pinia        |
| 请求   | Axios        |

---

## 3.2 后端技术

| 项目    | 技术             |
| ----- | -------------- |
| 语言    | Python 3.12    |
| 框架    | FastAPI        |
| ORM   | SQLAlchemy 2.x |
| 数据校验  | Pydantic V2    |
| 数据库迁移 | Alembic        |

---

## 3.3 AI工作流

采用：

LangGraph

原因：

* 支持多Agent流程；
* 支持状态保存；
* 支持节点编排；
* 支持未来扩展。

---

## 3.4 异步任务

采用：

Redis + Celery

用途：

* 视频生成；
* AI任务；
* 文件处理。

---

## 3.5 数据存储

### MySQL

保存：

业务数据。

例如：

用户。

项目。

视频。

---

### Redis

保存：

* 临时状态；
* 任务队列；
* 缓存。

---

### OSS

保存：

* 视频；
* 图片；
* 音频；
* 素材。

---

# 4. 系统模块设计

---

# 4.1 Identity Module

身份模块。

负责：

* 用户登录；
* 注册；
* 团队；
* 权限。

---

目录：

```text
identity/
├── models.py
├── schemas.py
├── service.py
└── api.py
```

---

# 4.2 Content Module

内容中心。

这是核心业务模块。

负责：

* 热点；
* 内容推荐；
* 内容分类；
* 内容评分。

---

目录：

```text
content/

├── recommendation.py
├── trend.py
├── scoring.py
└── api.py
```

---

# 4.3 Creation Module

创作中心。

负责：

* 创建项目；
* 管理脚本；
* 管理视频。

---

目录：

```text
creation/

├── project.py
├── script.py
├── video.py
└── api.py
```

---

# 4.4 AI Workflow Module

AI流程核心。

负责：

调用：

AI专家。

---

目录：

```text
workflow/

├── graph.py
├── nodes/
│
├── state.py
└── executor.py
```

---

# 4.5 AI Expert Module

AI专家管理。

目录：

```text
experts/

├── content_expert.py

├── planning_expert.py

├── script_expert.py

├── review_expert.py

├── video_expert.py

└── operation_expert.py
```

---

# 4.6 Knowledge Module

知识中心。

保存：

* Prompt；
* 行业知识；
* 规则。

---

目录：

```text
knowledge/

├── prompts/
├── rules/
└── documents/
```

---

# 4.7 Asset Module

素材中心。

管理：

* 真人素材；
* 视频素材；
* 图片；
* 音频。

---

# 4.8 Analytics Module

数据分析。

负责：

* 播放；
* 评论；
* 咨询；
* 转化。

---

# 5. AI工作流架构

核心流程：

```text
User Input

↓

Content Expert

↓

Planning Expert

↓

Script Expert

↓

Review Expert

↓

Video Expert

↓

Operation Expert

↓

Result
```

---

# 6. AI服务抽象层

非常重要。

禁止业务代码直接调用模型。

统一：

AI Provider。

---

结构：

```text
AI Service

├── LLM Provider

│    ├── GPT

│    ├── DeepSeek

│    └── Qwen


├── Voice Provider

│    ├── Azure Voice

│    └── Volcano


├── Video Provider

│    └── Digital Human API
```

---

以后：

换模型。

只改Provider。

---

# 7. 后端项目结构

最终：

```text
backend/

app/

├── main.py

├── api/

├── core/

├── models/

├── schemas/

├── services/

├── repositories/

├── workflow/

├── experts/

├── tasks/

├── prompts/

├── knowledge/

├── storage/

└── utils/
```

---

# 8. 前端项目结构

```text
frontend/

src/

├── views/

│
├── components/

├── api/

├── stores/

├── router/

├── assets/

├── utils/

└── layouts/
```

---

# 9. Docker部署架构

V1：

采用：

Docker Compose。

结构：

```text
docker-compose.yml


services:


frontend


backend


mysql


redis


worker


nginx
```

---

# 10. 安全设计

必须：

* JWT登录；
* 权限控制；
* API限流；
* 文件访问控制；
* AI调用日志。

---

# 11. 可扩展设计

未来增加：

## AI直播助手

新增：

Live Expert。

---

## AI私域助手

新增：

CRM Expert。

---

## AI课程助手

新增：

Education Expert。

---

无需重构。

---

# 12. V1开发原则

必须遵守：

## 原则1

先跑通闭环。

不要过度设计。

---

## 原则2

AI能力必须模块化。

---

## 原则3

所有任务异步化。

---

## 原则4

所有AI结果可追踪。

---

## 原则5

所有数据沉淀。

---

# 文档状态

版本：

V1.0

状态：

Approved（作为开发架构基准）

---

## 

进入：

# 《03-ER数据模型设计（Database Design）》

这一章我们会正式设计：

* MySQL数据库表；
* 字段；
* 主键；
* 外键；
* 索引；
* 表关系；
* SQLAlchemy模型结构。

完成这一章后，AI开发工具就可以自动生成：

* 数据库；
* 后端Model；
* API基础代码。

我们正式开始搭建第一块"地基"。
