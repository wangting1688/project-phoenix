# H3 照片生成讲解画面 —— project-Phoenix 对接说明

## 解决什么问题
现有 `video_producer` 管线：`文案 -> TTS -> 口型(lipsync) -> 渲染`，前提是已有**实拍素材 footage**。
本能力补上缺失的「画面生成」：**仅凭一张人像照片 + 文案 + 场景**，用本地
ComfyUI + MiniMax H3 生成画面与口型都已对齐的讲解视频，产出可作为 footage。

全本地：HTTP 调常驻 ComfyUI(8188) 与 CosyVoice(18080)，数据不出本机。

## 新增文件
| 文件 | 职责 | 依赖 |
|---|---|---|
| `app/services/h3_pipeline.py` | 核心流水线（定场图→逐句TTS→批量独立首帧i2v→等长裁切→硬切拼接→同源音轨）。纯 HTTP+ffmpeg，无 app 耦合 | requests, ffmpeg, ComfyUI, CosyVoice |
| `app/services/h3_video_engine.py` | Phoenix 风格薄封装：环境变量配置、落盘到 `storage/footage/h3/`、`SCENE_PRESETS`、健康检查 | 同上 |
| `app/services/h3_production_service.py` | 主后端用：调引擎生成并落库为 `Footage(source_type="ai_generated")` | 主后端(含DB) |
| `scripts/run_h3_engine.py` | 独立 worker CLI（仿 gpu_worker，按文件路径加载，绕开 app/__init__），用 `.venv_lipsync` 跑 | .venv_lipsync |

## 定稿算法（h3_pipeline.py，已实测）
1. (可选)定场图：人像照片经 H3 i2v(8步,39帧) 生成「人在场景里」锚点帧，抽 ~1.3s 帧；
   也可由人多跑候选人工选定后用 `--anchor` 指定（发型/场景最稳的做法）。
2. 文案按句号切句 → CosyVoice 逐句克隆配音（内置相似度门控重试）。
3. 每句时长→帧数，规则 `n%17==5`。
4. H3 i2v **批量独立首帧**：每段首帧都是同一张锚点图（无链式漂移、场景统一），
   音频锚点 `MiniMaxH3AddGuide` 喂该句，4 步 turbo，默认 512x960。
5. 每段 `ffmpeg -t <句时长> -an` **裁到与该句等长** → concat **硬切**（不用 xfade，
   xfade 会改时长导致累积错位）→ concat 同源 N 句音轨 → `-shortest` 合成。
   段边界=句边界，口型全程对齐。

## 调用方式

### A. 独立 worker（任务系统/子进程，已验证）
```
.venv_lipsync/Scripts/python.exe scripts/run_h3_engine.py \
  --person D:/.../person.png \
  --script D:/.../copy.txt \
  --scene park_walk \
  --anchor D:/.../scene_anchor.jpg \
  --out D:/.../final.mp4
```
`--scene` 可取预设 `park_walk/lecture/teahouse/street_walk`，或直接传英文描述。
默认测试档 512x960；定稿传 `--width 768 --height 960 倍数注意`（高宽须为 32 倍数，
768x1344 可用；640x1136 会 shape 报错）。

### B. 主后端 service（落库 Footage）
```python
from app.services.h3_production_service import H3ProductionService
svc = H3ProductionService(storage_root=BACKEND, db=db)
footage = svc.generate_and_register(
    user_id=uid, person_image=..., script_text=..., scene=SCENE_PRESETS["park_walk"],
    anchor_image=..., hair_hint="undercut upward-swept top, short sides")
# footage.id 即可传给现有视频生产流程
```

## 接入 video_producer 的最小改法（建议，尚未改动核心代码）
现状 `create_task(...footage_id, with_lipsync=True)` 强依赖实拍素材，且
`_render_video -> render_video(tts_audio_path=tts_path)` 会用新 TTS 音轨覆盖素材自带音轨。
H3 footage 已含「画面+对齐音轨」，接入时需要：
1. `create_task` 增加可选 `visual_source`（默认 "footage"；新值 "h3_generate"）
   与 `person_image/scene/anchor_image/hair_hint` 等参数（存入 task params）。
2. `run()` 在取 footage 前：若 `visual_source=="h3_generate"`，先调
   `H3ProductionService.generate_and_register()` 拿到 footage，且 **`with_lipsync=False`**，
   并跳过 producer 自己的 `_generate_tts`（H3 已逐句配音）。
3. 渲染层 `video_renderer.render_video` 增加一个「保留素材自带音轨」开关
   （`use_source_audio=True` 时不铺 tts_audio_path）——这是唯一需要动渲染层的点。
未做这步前，H3 成片请直接使用 `storage/footage/h3/*.mp4`（已可独立交付），
不要直接喂给会重做 TTS 的完整 producer，否则音轨被覆盖、口型可能错位。

## 环境变量（均有本机默认）
`H3_COMFY_URL`(8188) `H3_TTS_URL`(18080/tts) `H3_REF_WAV`(D:/phx_tts/ref.wav)
`H3_FFMPEG` `H3_COMFY_INPUT/OUTPUT` `H3_TEST_RES`(默认 512x960)

## 运维前提
ComfyUI 需常驻（含 MiniMax H3 fl2va int8、4/8步 turbo LoRA）。调用前
`H3VideoEngine.health()` ping `/system_stats`；建议像 18080 一样做开机自启+健康检查。
显存：测试档 512x960/4步 50秒10段约6分钟；**禁止单段50秒(1229帧)**，24GB 会崩。
