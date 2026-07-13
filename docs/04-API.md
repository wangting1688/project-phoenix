很好，我们继续进入下一份核心开发文档。

现在我们已经有：

✅ PRD（产品需求）
✅ Architecture（系统架构）
✅ Database（数据库设计）

下一步就是连接前端和后端的桥梁：

# API接口设计文档

---

# Project Phoenix

# AI短视频操作系统

## API Design Document

**文件名：04-API.md**

**版本：V1.0 MVP**

---

# 1. API设计原则

## 1.1 基础规范

协议：

HTTP REST API

格式：

JSON

字符：

UTF-8

---

## 1.2 API地址

开发环境：

```
http://localhost:8000/api/v1
```

生产环境：

```
https://api.xxx.com/api/v1
```

---

# 2. 通用返回格式

所有接口统一：

成功：

```json
{
  "code":200,
  "message":"success",
  "data":{}
}
```

失败：

```json
{
  "code":400,
  "message":"错误原因",
  "data":null
}
```

---

# 3. 用户认证接口

---

# 3.1 用户登录

## POST

```
/auth/login
```

---

请求：

```json
{
 "phone":"13800000000",
 "password":"123456"
}
```

---

返回：

```json
{
 "token":"xxxxx",
 "user":{
    "id":1,
    "nickname":"张姐",
    "role":"anchor"
 }
}
```

---

# 3.2 获取当前用户

GET

```
/auth/me
```

返回：

```json
{
"id":1,
"nickname":"张姐",
"avatar":"",
"content_profile":{
 "style":"故事型",
 "category":"健康"
}
}
```

---

# 4. 创作中心接口（核心）

---

# 4.1 创建创作项目

这是整个系统最重要接口。

## POST

```
/creation/projects
```

---

请求：

```json
{
 "source_type":"custom",
 "topic":"睡眠不好怎么办"
}
```

---

source_type：

```text
recommend

viral_analysis

custom
```

---

返回：

```json
{
 "project_id":10001,
 "task_id":90001,
 "status":"processing"
}
```

---

说明：

创建项目后：

进入AI Workflow。

---

# 5. AI任务接口

---

# 5.1 查询任务状态

GET

```
/tasks/{task_id}
```

---

返回：

```json
{
 "task_id":90001,
 "status":"running",
 "progress":60,
 "current_step":"生成文案"
}
```

---

状态：

```text
waiting

running

success

failed
```

---

# 5.2 获取任务结果

GET

```
/tasks/{task_id}/result
```

---

返回：

```json
{
 "project_id":10001,

 "scripts":[
 {
  "type":"story",
  "content":"..."
 },
 {
  "type":"knowledge",
  "content":"..."
 }
 ],

 "video":{
  "url":"xxx.mp4"
 }
}
```

---

# 6. AI推荐接口

---

# 6.1 获取今日推荐

GET

```
/content/recommendations
```

---

参数：

```
category=health
```

---

返回：

```json
[
 {
  "level":"A",
  "title":"睡眠成为近期热门",
  "reason":"45岁女性关注增长"
 },
 {
  "level":"B",
  "title":"肠道健康"
 }
]
```

---

# 6.2 推荐分类

GET

```
/content/categories
```

返回：

```json
[
"健康知识",
"养生",
"情绪",
"家庭",
"生活",
"美食"
]
```

---

# 7. 爆款解析接口

---

# 7.1 提交视频链接

POST

```
/analysis/video
```

---

请求：

```json
{
"url":
"https://xxx.com/video/123"
}
```

---

返回：

```json
{
"task_id":80001
}
```

---

后台执行：

```text
视频解析

↓

提取结构

↓

分析爆点

↓

生成原创方案
```

---

# 8. 文案接口

---

# 8.1 获取文案列表

GET

```
/projects/{project_id}/scripts
```

---

返回：

```json
[
{
"type":"story",
"score":92,
"content":"..."
}
]
```

---

# 8.2 重新生成文案

POST

```
/projects/{project_id}/scripts/regenerate
```

---

请求：

```json
{
"type":"story",
"feedback":"更生活化"
}
```

---

返回：

新的script。

---

# 9. 视频接口

---

# 9.1 生成视频

POST

```
/projects/{project_id}/video
```

---

请求：

```json
{
"script_id":10001,
"voice":"female",
"style":"daily"
}
```

---

返回：

```json
{
"task_id":70001
}
```

---

# 9.2 获取视频

GET

```
/projects/{project_id}/video
```

---

返回：

```json
{
"url":"xxx.mp4",
"cover":"xxx.jpg"
}
```

---

# 10. 素材接口

---

# 10.1 上传真人素材

POST

```
/assets/upload
```

---

支持：

图片。

视频。

音频。

---

返回：

```json
{
"asset_id":50001,
"url":"xxx"
}
```

---

# 11. 作品管理接口

---

# 11.1 我的作品

GET

```
/projects
```

---

参数：

```
page=1
size=20
```

---

返回：

```json
[
{
"id":10001,
"topic":"睡眠",
"status":"completed"
}
]
```

---

# 12. 数据分析接口

---

# 12.1 视频数据

GET

```
/analytics/videos/{video_id}
```

---

返回：

```json
{
"views":100000,
"likes":5000,
"comments":300,
"consultations":80
}
```

---

# 13. AI Memory接口

---

# 13.1 获取主播画像

GET

```
/memory/profile
```

---

返回：

```json
{
"style":"故事型",
"audience":"45岁女性",
"topics":[
"睡眠",
"家庭"
]
}
```

---

# 13.2 更新偏好

POST

```
/memory/profile
```

---

请求：

```json
{
"favorite_style":"聊天型"
}
```

---

# 14. 管理后台接口（V1基础）

---

## Prompt管理

GET

```
/admin/prompts
```

---

## 知识库管理

GET

```
/admin/knowledge
```

---

# 15. 核心创作流程API时序

这是系统最重要流程：

```text
用户

↓

POST /creation/projects

↓

返回task_id

↓

GET /tasks/{id}

↓

Workflow执行

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

完成

↓

GET result

↓

下载视频
```

---

# 16. API版本规划

当前：

```
/api/v1
```

未来：

```
/api/v2
```

保证兼容。

---

# API设计完成

状态：

Approved

---

## 下一步

进入：

# 《05-AI Workflow设计文档》

这一章是整个产品最核心的部分。

我们会详细设计：

* AI内容专家怎么工作；
* 爆款分析流程；
* 文案生成流程；
* 审核流程；
* 视频生成流程；
* AI Memory如何学习主播；
* LangGraph节点设计。

完成这一章后，我们就拥有真正的 AI 大脑设计图。下一步开始进入 AI 核心开发。
