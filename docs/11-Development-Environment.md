很好。

到这里，我们已经完成了产品设计阶段。

从下一步开始，我们进入**真正的工程实施阶段**。

这一章非常重要，因为你的开发方式不是传统外包，而是：

> 你作为产品负责人 + AI作为开发团队。

所以我们需要先建立一个稳定的 AI 协同开发环境。

---

# Project Phoenix

# AI短视频操作系统

# 开发环境搭建与AI协同开发指南

**文件名：11-Development-Environment.md**

**版本：V1.0**

---

# 1. 开发模式说明

## 1.1 团队角色重新定义

未来开发团队：

| 角色               | 负责           |
| ---------------- | ------------ |
| 你（产品负责人）         | 需求、方向、验收     |
| ChatGPT（架构顾问）    | 架构、任务拆解、代码审查 |
| Trae / WorkBuddy | 代码生成、修改、调试   |
| AI模型             | 具体开发执行       |
| 服务器              | 运行环境         |

---

# 2. 开发原则

以后所有开发遵守：

## 原则1

先文档。

后代码。

---

## 原则2

一个功能一个任务。

不要一次让AI开发整个系统。

---

## 原则3

每次修改必须可回滚。

---

## 原则4

代码必须能运行。

不接受：

“理论代码”。

---

# 3. 本地开发环境

## 3.1 必备软件

---

## 编辑器

推荐：

### Trae

用途：

主要代码开发。

---

### WorkBuddy

用途：

快速生成、修改代码。

---

## 浏览器

Chrome。

---

## 终端

Mac:

Terminal

Windows:

PowerShell

---

# 4. 安装基础环境

---

# 4.1 Python

版本：

Python 3.12+

---

检查：

```bash
python --version
```

结果：

```text
Python 3.12.x
```

---

# 4.2 Node.js

版本：

Node.js 22+

---

检查：

```bash
node -v
```

---

# 4.3 Git

检查：

```bash
git --version
```

---

# 4.4 Docker

安装：

Docker Desktop

---

检查：

```bash
docker --version
```

---

# 5. 创建项目目录

项目名称：

AI短视频操作系统。

代码名称：

Project Phoenix。

---

目录：

```text
project-phoenix/

├── docs/

├── backend/

├── frontend/

├── workflow/

├── scripts/

└── README.md
```

---

解释：

## docs

存放：

全部开发文档。

---

## backend

Python后端。

---

## frontend

Vue前端。

---

## workflow

AI流程。

---

## scripts

自动化脚本。

---

# 6. 初始化Git

进入项目：

```bash
cd project-phoenix
```

初始化：

```bash
git init
```
