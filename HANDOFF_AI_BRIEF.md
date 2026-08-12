# Project Phoenix 交接说明（给接手的 AI 编程助理）

> 用途：我在另一台电脑上接手本项目，请 AI 助理依据此说明继续推进，重点是「口型同步（Wav2Lip）在 32GB GPU 新主机上跑通」。

---

## 一、这是什么项目
**Project Phoenix** —— 一个短视频 AIGC 创作平台（SaaS）。用户走「创作向导」：选主题 → 选声音 → 上传/选素材 → 生成脚本 → 合成视频（含 TTS 配音 + 口型同步）→ 出片，并附带「运营方案」展示。

---

## 二、技术栈与部署架构
- **前端**：Vue3 + Vite5 + Element Plus（SPA，步骤机 `currentStep` 0→4）。
- **后端**：FastAPI + uvicorn + SQLite。
- **静态资源**：走带 token 鉴权的 `/static/{path}`；`request` 拦截器返回整个 `ApiResponse({code,message,data})`，前端须取 `res.data`。
- **线上服务器**：阿里云 `106.15.66.71`，站点 `shipin.sdzunyue.wang`（nginx 80/443）。后端 `phoenix.service`（systemd），端口 8110，Python 3.11（在 `/www/phoenix/backend/.venv`）。DB：`/www/phoenix/backend/data/phoenix.db`（SQLite）。
- **代码仓库**：`git@github.com:wangting1688/project-phoenix.git`，`main` 分支（最新 `ce5dae1`）。
- **原开发机（mac）**：`/Users/mac/Desktop/Project Phoenix`。

---

## 三、近期已完成的修复（都已上线验证，可不复做）
1. **创作向导各环节**：声音试听（接 `testVoiceProfile` + `<audio>` 播放）、素材列表解析（`res.data.items` 取错路径已修）、视频缩略图带 token 加载（`addTokenToUrl`）、生成步 404（线上 `video.py` 是旧版缺 `/generate` 路由，已对齐 11 个分叉文件 + DB 加 `deleted_at` 列）。
2. **运营方案空白**：`result/index.vue` 在 `project` 分支从不调用 `loadOperationData()`，导致区块虽显示但标题/标签全空。已修复——project 分支主动加载，标题优先取项目真实主题。线上临时置某 project 为 `completed` 实测渲染出 7 条内容 + 8 个标签，PASS 后已还原数据。

---

## 四、当前最关键的待办：口型同步（Wav2Lip）
**现象**：生成视频「口型对不上」。

**根因**：
- 渲染器把素材原音轨**静音**，只叠加 TTS 配音；
- 线上服务器**无 wav2lip 模型 / torch / cv2 / librosa**；
- 旧的 `lipsync_runner.py` 里是**手写的假 U-Net**（非真实 Wav2Lip 结构），即使有模型也对不上。

**已做的修复（已提交 GitHub，尚未在 GPU 上真正生效）**：
- `backend/app/services/lipsync_service.py` 重写为调用**【官方 Wav2Lip inference.py】**（与 `wav2lip_gan.pth` 严格对应）；支持 `LIPSYNC_REMOTE_SSH` 把推理派发到 GPU 机；`torch` 等依赖**惰性导入**，CPU 环境自动静默跳过、不崩。
- 删除手写假网络；`lipsync_runner.py` 降为「弃用说明」桩。
- 新增 `backend/scripts/setup_lipsync_gpu.sh`：一键装 torch+cuda、`git clone` 官方 Wav2Lip 仓库、下载 `wav2lip_gan.pth`。

**为什么必须上 GPU**：真实 Wav2Lip 只能在 GPU 上跑（N 卡 CUDA 最佳；Apple Silicon 需改 MPS 后端，速度慢）。当前线上是 CPU 服务器，本地开发机也无 GPU。

---

## 五、在 GPU 新主机上要继续做的事（方案 A：本地整体跑生成）
**前提**：用户新装了一台 **32GB GPU 主机**（假设 NVIDIA + Linux）。目标：让真实 Wav2Lip 跑通口型同步。

**给 AI 的具体执行指令**：
1. 在该机 `git clone` 上面仓库，进入 `backend/`。
2. 建 venv（python3.11），装依赖（先查有没有 `requirements.txt`；没有就按 `setup` 脚本 / 实际 imports 补齐）。
3. 跑 `bash backend/scripts/setup_lipsync_gpu.sh` 完成 GPU 环境 + 官方 Wav2Lip 仓库 + 模型权重。
4. 用一段样例素材实测口型是否对上（调用 `lipsync_service` 的 `sync` 接口/函数；确认视频里人物嘴型与 TTS 声音对齐）。
5. 打通「远程提交 → 本地 GPU 跑完整生成 → 返回视频」：
   - 本地起后端，前端 `API` 地址指向本机**公网地址**（用 Cloudflare Tunnel / ngrok 暴露，无需公网 IP、不用改路由器）；
   - 视频生成完自动上传对象存储（OSS/COS）或经隧道返回公共 URL，供远程浏览器播放。
6. 端到端验证：从网站提交一个生成任务，确认视频口型对齐、运营方案正常显示。

> 备选方案 B（线上派发）已否决：它要求线上服务器反向 SSH 连回本地 GPU，网络麻烦且线上仍参与全流程，不如 A 顺。

---

## 六、重要坑 / 约定（别踩）
- **线上后端是 Python 3.11**（在 `.venv` 里），不是系统自带的 3.6；所以 `from __future__ import annotations` 没问题——但 lipsync 文件已去掉这行做防御性加固。
- **前端构建必须** `npx vite build` 跳过 `vue-tsc`（类型检查与当前 node 版本不兼容会卡死）。
- **部署后端**：保留线上 `.env` 和 `data/`，只覆盖 `app/` 和 `scripts/`；改前先 `cp -r` 备份。
- **提交代码**：`.env`（含 `SECRET_KEY` 等）已被 gitignore；`.workbuddy/`、`backend/storage/`(视频/模型)、`node_modules/`、日志/备份都已排除。**不要 `git add .` 一把梭**，避免把密钥/大文件推上去。
- **JWT**：线上密钥在 `/www/phoenix/backend/.env`，载荷为 `{"sub": str(user_id)}`，HS256。
- **静态资源需带 token** 访问，前端用 `addTokenToUrl` 处理。
- **验证用真实浏览器**：创作向导/结果页的问题建议用 Agent-Browser 或系统 Chrome 走真实登录链路验证，并提醒用户强刷（Cmd+Shift+R）。

---

## 七、需要用户补充的信息
- GPU 新主机的 **系统 + 显卡型号**（NVIDIA / Apple Silicon？决定走 CUDA 还是改 MPS）；
- 是否可**提供 SSH 访问**（IP + 密钥），便于直接跑 `setup_lipsync_gpu.sh` 并实测口型。
