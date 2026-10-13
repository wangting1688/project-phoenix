# -*- coding: utf-8 -*-
"""
h3_video_engine.py — project-Phoenix 的「H3 照片生成讲解画面」引擎（薄封装）

定位：
  Phoenix 现有 video_producer 管线是  文案 -> TTS -> 口型(lipsync引擎) -> 渲染，
  前提是已有实拍素材 footage。本引擎补上缺失的「画面生成」环节：
  仅凭一张人像照片 + 文案 + 场景描述，用本地 ComfyUI + MiniMax H3 生成
  画面与口型都已对齐的讲解视频，产出可直接作为 footage 进入现有渲染链路。

  与 lipsync 引擎的区别（为什么不是并列成一个 lipsync 引擎）：
  - lipsync 引擎输入「已有真人视频」，只重绘嘴部；
  - 本引擎输入「一张照片」，生成整段画面（场景/表情/手势/口型），应插在 footage 之前。

全本地：HTTP 调常驻 ComfyUI(8188) 与 CosyVoice(18080)，数据不出本机。
核心算法在同目录 h3_pipeline.py，本文件只做 Phoenix 侧配置/路径/落盘适配。

环境变量（均有本机默认值）：
  H3_COMFY_URL       默认 http://127.0.0.1:8188
  H3_TTS_URL         默认 http://127.0.0.1:18080/tts
  H3_REF_WAV         CosyVoice 参考音色（默认 D:/phx_tts/ref.wav）
  H3_FFMPEG          ffmpeg.exe 路径
  H3_COMFY_INPUT/OUTPUT  ComfyUI 输入输出目录
  H3_TEST_RES        分辨率，测试档默认 "512x960"（定稿再升 768x1344）
"""
from __future__ import annotations
import os
import json
import time
import uuid
from pathlib import Path
from typing import Optional

def _load_h3():
    # 兼容两种宿主：主后端(包相对导入) 与独立 GPU worker(按文件路径加载，绕开 app/__init__)
    try:
        from . import h3_pipeline as m
        return m
    except Exception:
        import importlib.util
        p = Path(__file__).with_name("h3_pipeline.py")
        spec = importlib.util.spec_from_file_location("h3_pipeline", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m


P = _load_h3()


def _env(k: str, d: str) -> str:
    return os.environ.get(k, d).strip() or d


class H3VideoEngine:
    name = "h3_generate"

    def __init__(self, storage_root: Path):
        self.storage_root = Path(storage_root)
        # 用环境变量覆盖核心模块常量
        P.COMFY_URL = _env("H3_COMFY_URL", P.COMFY_URL)
        P.TTS_URL = _env("H3_TTS_URL", P.TTS_URL)
        P.REF_WAV = _env("H3_REF_WAV", P.REF_WAV)
        P.FFMPEG = _env("H3_FFMPEG", P.FFMPEG)
        P.COMFY_INPUT = _env("H3_COMFY_INPUT", P.COMFY_INPUT)
        P.COMFY_OUTPUT = _env("H3_COMFY_OUTPUT", P.COMFY_OUTPUT)
        res = _env("H3_TEST_RES", "512x960").lower().split("x")
        self.default_w, self.default_h = int(res[0]), int(res[1])
        # 统一落盘目录：storage/footage/h3/
        self.out_dir = self.storage_root / "storage" / "footage" / "h3"
        self.work_root = self.storage_root / "storage" / "tmp" / "h3"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.work_root.mkdir(parents=True, exist_ok=True)

    def health(self) -> bool:
        import requests
        url = os.environ.get("H3_REMOTE_HTTP", "").strip()
        try:
            if url:
                # 远程(本机 GPU worker 经反向隧道暴露)：探 /h3/health
                return requests.get(url.rstrip("/") + "/h3/health", timeout=10).status_code == 200
            return requests.get(P.COMFY_URL + "/system_stats", timeout=6).status_code == 200
        except Exception:
            return False

    def available(self) -> bool:
        return self.health()

    # ---- 远程派发（生产：Phoenix 在服务器，ComfyUI 在本地 GPU 机）----
    def _generate_remote(self, person_image, script_text, scene, anchor_image,
                         width, height, hair_hint, seed, job, emphasis=None,
                         ref_wav=None, ref_text=""):
        """把照片+文案+场景经隧道 POST 给 GPU worker 的 /h3/generate，回收 mp4。"""
        import requests
        base = os.environ["H3_REMOTE_HTTP"].strip().rstrip("/")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.out_dir / f"{job}.mp4"
        data = {"text": script_text, "scene": _scene_key(scene),
                "hair_hint": hair_hint or "", "seed": str(int(seed or 400000))}
        if emphasis:
            data["emphasis"] = json.dumps(emphasis, ensure_ascii=False)
        if ref_text:
            data["ref_text"] = ref_text
        if width: data["width"] = str(width)
        if height: data["height"] = str(height)
        files = {"person": ("person" + Path(person_image).suffix,
                            open(person_image, "rb"), "application/octet-stream")}
        if anchor_image:
            files["anchor"] = ("anchor" + Path(anchor_image).suffix,
                               open(anchor_image, "rb"), "application/octet-stream")
        if ref_wav:
            files["ref_wav"] = ("ref.wav", open(ref_wav, "rb"), "audio/wav")
        try:
            # 长任务：50秒测试档约6-10分钟，给足余量
            r = requests.post(base + "/h3/generate", data=data, files=files, timeout=3600)
        finally:
            for f in files.values():
                f[1].close()
        if r.status_code != 200 or "video" not in r.headers.get("content-type", ""):
            # worker 的失败响应是 {"error":..., "detail": "人话原因"}。
            # 直接把整个 JSON 抛给用户会得到一串看不懂的原始报文，
            # 这里优先取 detail，只把技术字段留在日志里。
            try:
                body = r.json()
                detail = (body or {}).get("detail") or (body or {}).get("error") or ""
            except Exception:
                detail = ""
            if not detail:
                detail = r.text[:300]
            raise RuntimeError(f"视频生成失败：{detail}")
        out_path.write_bytes(r.content)
        return out_path

    def generate(
        self,
        person_image: str,
        script_text: str,
        scene: str,
        *,
        anchor_image: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        hair_hint: str = "",
        seed: int = 400000,
        job_id: Optional[str] = None,
        emphasis: Optional[list] = None,
        ref_wav: Optional[str] = None,
        ref_text: str = "",
    ) -> Path:
        """
        生成讲解视频。

        参数：
          person_image  人像照片（脸/发型来源）
          script_text   讲解文案（按句号切句、逐句克隆配音）
          scene         英文场景+动作描述（如 "walking along a park path..., background..."）
          anchor_image  可选：人工选定的统一场景定场帧；不给则自动生成
          width/height  分辨率（默认 512x960 测试档，可用 H3_TEST_RES 覆盖）
          hair_hint     可选英文发型锁定描述
          seed          随机种子基址
          job_id        业务任务 id，用于隔离中间文件
        返回：成片 mp4 的 Path（storage/footage/h3/<job>.mp4）
        """
        job = job_id or time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        final = self.out_dir / f"{job}.mp4"

        # 生产模式：ComfyUI/GPU 不在本机，派发给隧道后的 GPU worker
        if os.environ.get("H3_REMOTE_HTTP", "").strip():
            return self._generate_remote(person_image, script_text, scene,
                                         anchor_image, width, height,
                                         hair_hint, seed, job, emphasis,
                                         ref_wav, ref_text)

        workdir = self.work_root / job
        pipe = P.H3Pipeline(workdir=str(workdir), comfy_url=P.COMFY_URL,
                            tts_url=P.TTS_URL,
                            ref_wav=ref_wav or P.REF_WAV,
                            ref_text=ref_text)
        pipe.run(
            person_image=person_image,
            script_text=script_text,
            scene=scene,
            final_output=str(final),
            anchor_image=anchor_image,
            width=width or self.default_w,
            height=height or self.default_h,
            hair_hint=hair_hint,
            seed_base=seed,
            emphasis=emphasis,
        )
        return final


# 场景预设：调用方可直接引用，保证不同任务场景描述一致

def _scene_key(scene_desc: str) -> str:
    """英文场景描述反查预设 key；查不到就原样传(worker会再映射/直接用)。"""
    for k, v in SCENE_PRESETS.items():
        if scene_desc and scene_desc.strip() == v.strip():
            return k
    return scene_desc or "lecture"

SCENE_PRESETS = {
    "park_walk": ("walking along a park path mid-stride with one arm swinging, "
                  "background of a lush green park with trees, grass and a walkway softly blurred, "
                  "warm natural daylight, shallow depth of field"),
    "lecture": ("standing and giving a health lecture on a seminar stage with minimal body movement, "
                "background of a softly blurred lecture hall with warm stage light and a faint projection screen, "
                "shallow depth of field"),
    "teahouse": ("sitting in a warm Chinese-style tea room speaking gently, "
                 "background of wooden tea table and shelves softly blurred, soft warm light, shallow depth of field"),
    "street_walk": ("walking forward on a modern commercial shopping street with an easy gait, "
                    "background of storefronts and blurred pedestrians, bright daylight, shallow depth of field"),
    "kitchen": ("standing in a bright home kitchen speaking while holding a cup, "
                "background of kitchen counter and cabinets softly blurred, warm daylight, shallow depth of field"),
    "office": ("sitting at a tidy office desk speaking professionally, "
               "background of office shelves and soft window light softly blurred, shallow depth of field"),
    "living_room": ("sitting on a cozy sofa in a warm living room speaking naturally, "
                    "background of soft sofa cushions and warm lamps softly blurred, shallow depth of field"),
    "balcony_garden": ("standing on a sunlit balcony surrounded by green potted plants speaking cheerfully, "
                       "background of soft daylight and blurred city view, shallow depth of field"),
    "study": ("sitting in a study with a bookshelf wall behind, speaking calmly like sharing notes, "
              "background of blurred books and warm desk lamp, shallow depth of field"),
    "cafe": ("sitting at a cozy cafe table with a cup of coffee speaking in a friendly tone, "
             "background of blurred cafe interior and warm light, shallow depth of field"),
    "gym": ("standing in a bright gym with fitness equipment in the blurred background, "
            "speaking energetically about health and exercise, shallow depth of field"),
}

