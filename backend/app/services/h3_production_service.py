# -*- coding: utf-8 -*-
"""
h3_production_service.py — 把 H3 画面生成接入 project-Phoenix 的素材/生产体系

职责（运行在主后端，可访问 DB）：
  1. 调 H3VideoEngine：一张人像照片 + 文案 + 场景 -> 画面/口型已对齐的讲解视频
  2. 落库为一条 Footage(source_type="ai_generated")，之后可直接用其 footage_id
     走现有 video_producer 渲染链路（建议 with_lipsync=False：H3 口型已对齐，
     不必再过 latentsync；渲染阶段不要再用新 TTS 覆盖其音轨）。

独立 GPU 推理仍发生在 ComfyUI 进程，本服务只做 HTTP 编排 + 落库，不占后端显存。
"""
from __future__ import annotations
import importlib.util
import subprocess
from pathlib import Path
from typing import Optional

_SERVICES = Path(__file__).resolve().parent


def _load(mod_name, file_name):
    p = _SERVICES / file_name
    spec = importlib.util.spec_from_file_location(mod_name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _probe(ffmpeg: str, path: Path, what: str):
    p = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True, errors="replace")
    import re
    if what == "duration":
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", p.stderr)
        return int(float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))) if m else 0
    if what == "resolution":
        m = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", p.stderr)
        return f"{m.group(1)}x{m.group(2)}" if m else None
    return None


class H3ProductionService:
    def __init__(self, storage_root: Path, db=None):
        self.storage_root = Path(storage_root)
        self.db = db
        engine_mod = _load("h3_video_engine", "h3_video_engine.py")
        self.engine = engine_mod.H3VideoEngine(self.storage_root)
        self.ffmpeg = engine_mod.P.FFMPEG

    def generate_and_register(
        self,
        *,
        user_id: int,
        person_image: str,
        script_text: str,
        scene: str,
        category_id: Optional[int] = None,
        anchor_image: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        hair_hint: str = "",
        seed: int = 400000,
        scene_tag: Optional[str] = None,
        action_tag: Optional[str] = None,
    ):
        """生成 H3 讲解视频并落库为 Footage，返回 Footage ORM 对象。"""
        if self.db is None:
            raise RuntimeError("H3ProductionService 需要 db session")
        if not self.engine.available():
            raise RuntimeError("ComfyUI(8188) 不在线，无法生成 H3 画面")

        video: Path = self.engine.generate(
            person_image=person_image,
            script_text=script_text,
            scene=scene,
            anchor_image=anchor_image,
            width=width, height=height, hair_hint=hair_hint, seed=seed,
        )

        # file_path 用相对 storage_root 的路径，_get_footage_path 能直接命中
        rel = video.relative_to(self.storage_root).as_posix()
        from app.models.footage import Footage
        footage = Footage(
            user_id=user_id,
            category_id=category_id,
            filename=video.name,
            file_path=rel,
            thumbnail=None,
            duration=_probe(self.ffmpeg, video, "duration"),
            resolution=_probe(self.ffmpeg, video, "resolution"),
            file_size=video.stat().st_size,
            scene=scene_tag,
            action=action_tag,
            status="ready",
            source_type="ai_generated",
            source_ref=f"h3:{video.stem}",
        )
        self.db.add(footage)
        self.db.commit()
        self.db.refresh(footage)
        return footage
