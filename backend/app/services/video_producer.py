"""
短视频生产编排服务 - MVP 核心

职责：串联视频生产全流程
  选题 → 文案生成 → TTS配音 → 口型同步 → 视频渲染 → 输出成片

设计原则：
- 每个环节都是独立服务（可替换）
- 异步任务化（通过 workflow_tasks 追踪进度）
- 失败降级：口型同步失败不阻塞主流程
- 可测试：每个步骤独立可调用

调用关系：
  API → VideoProducer (编排)
    ├── AIExpertService.script_expert (AI文案生成)
    ├── voice_clone.py (TTS配音)
    ├── lipsync_service.py (口型同步，独立服务)
    └── video_renderer.py (ffmpeg剪辑)
"""

from __future__ import annotations

import re
import threading
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import logging

from app.core.database import SessionLocal
from app.models.content import ContentProject, WorkflowTask, Script, Video

logger = logging.getLogger(__name__)


class ScriptDegradedError(RuntimeError):
    """AI 文案降级为写死模板。属于必须让用户知道的失败，不可静默继续。"""


# 段落骨架标记：【黄金开头】【故事】【价值输出】【互动】以及
# "第一部分：" 这类编号前缀。它们只用于组织结构，不属于口播内容。
_MARKER_RE = re.compile(
    r"[【\[](?:黄金开头|开头|故事|价值输出|价值|互动|结尾|钩子|第[一二三四五六]部分)[^】\]]*[】\]]"
    r"|第[一二三四五六]部分\s*[:：]"
)


def _strip_structure_markers(text: str) -> str:
    """移除文案里的结构标记，返回可直接朗读的正文。"""
    if not text:
        return text
    cleaned = _MARKER_RE.sub("", text)
    # 标记独占一行时会留下空行，顺手合并
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    lines = [ln.strip() for ln in cleaned.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


class VideoProducer:
    """短视频生产编排器"""

    def __init__(self, project_id: int, user_id: int = None):
        self.project_id = project_id
        self.user_id = user_id
        self.db = SessionLocal()
        self.storage_root = Path(__file__).resolve().parent.parent.parent

    def close(self):
        if self.db:
            self.db.close()

    # ------------------------------------------------------------------
    # 入口：创建并启动生产任务
    # ------------------------------------------------------------------

    @classmethod
    def create_task(
        cls,
        project_id: int,
        user_id: int,
        script_id: int,
        voice_profile_id: int,
        footage_id: int,
        with_lipsync: bool = True,
    ) -> int:
        """
        创建视频生产任务（异步），返回 task_id。
        实际生产在后台线程执行。
        """
        db = SessionLocal()
        try:
            # 创建/获取 task
            task = db.query(WorkflowTask).filter(
                WorkflowTask.project_id == project_id,
                WorkflowTask.task_type == "video_production",
            ).first()
            if not task:
                task = WorkflowTask(
                    project_id=project_id,
                    task_type="video_production",
                    status="waiting",
                    progress=0,
                )
                db.add(task)
            else:
                task.status = "waiting"
                task.progress = 0
                task.result = None
                task.error_message = None
            # 存一下参数
            task.result = json.dumps({
                "script_id": script_id,
                "voice_profile_id": voice_profile_id,
                "footage_id": footage_id,
                "with_lipsync": with_lipsync,
            }, ensure_ascii=False)
            db.commit()
            db.refresh(task)
            task_id = task.id
        finally:
            db.close()

        # 后台异步执行
        def _run():
            producer = cls(project_id, user_id)
            try:
                producer.run(task_id)
            except Exception as e:
                logger.exception("task=%s 后台线程未捕获异常", task_id)
            finally:
                producer.close()

        threading.Thread(target=_run, daemon=True).start()
        return task_id

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def run(self, task_id: int):
        """执行完整生产流程"""
        task = self._get_task(task_id)
        if not task:
            logger.warning("task=%s 不存在，终止生产", task_id)
            return

        params = {}
        try:
            params = json.loads(task.result or "{}")
        except Exception:
            pass

        try:
            # Step 1: 准备脚本（无则调用现有文案生成能力生成）
            self._update_task(task_id, "running", 5, "准备/生成文案")
            script = self._get_script(params.get("script_id"))
            if not script:
                logger.info("task=%s 未找到指定脚本，尝试自动生成文案", task_id)
                script = self._generate_script(task_id)
            if not script:
                raise ValueError("脚本不存在且无法自动生成（项目缺少选题 topic 或 AI 文案生成失败）")

            # Step 2: 先取素材 —— 本地音色克隆要用同一条素材里的人声做参考音频，
            # 所以素材必须在 TTS 之前就位（顺序与火山方案相反）
            footage_path = self._get_footage_path(params.get("footage_id"))
            if not footage_path:
                raise ValueError("素材不存在")

            # Step 3: TTS 生成配音
            self._update_task(task_id, "running", 20, "生成配音")
            tts_path = self._generate_tts(
                script.content,
                params.get("voice_profile_id"),
                footage_path=footage_path,
            )
            if not tts_path:
                raise RuntimeError("配音生成失败")

            # Step 3.5: 口型同步
            #
            # ⚠️ 这里曾经是「失败就静默降级用原素材」，任务照样标记 completed。
            # 后果很严重：用户拿到一个看起来正常、但嘴型和配音毫无关系的成片，
            # 界面上没有任何提示（线上任务 33 即如此，真因是显存不足）。
            # 口型是本产品的核心卖点，明确报失败让用户重试，
            # 远好于交付一个不可用的成片。
            synced_footage = None
            lipsync_requested = bool(params.get("with_lipsync", True))
            lipsync_error = None
            if lipsync_requested:
                self._update_task(task_id, "running", 45, "对齐口型")
                try:
                    synced_footage = self._run_lipsync(footage_path, tts_path)
                    if synced_footage is None:
                        lipsync_error = "口型同步未产出结果"
                except Exception as e:
                    lipsync_error = f"口型同步失败：{e}"
                    logger.exception("task=%s 口型同步失败", task_id)

                if synced_footage is None:
                    # 不再静默降级。显存不足是最常见原因，且重试通常能成功。
                    raise RuntimeError(
                        f"{lipsync_error or '口型同步失败'}。"
                        "常见原因是显卡显存被占用，请稍后重试；"
                        "若持续失败请联系管理员查看 GPU worker 日志。"
                    )

            # 最终用的素材路径（未启用口型时用原素材）
            final_footage = synced_footage or footage_path

            # Step 4: 视频渲染（ffmpeg 拼接+字幕+配音）
            self._update_task(task_id, "running", 75, "合成视频")
            result = self._render_video(
                script=script.content,
                footage_path=final_footage,
                tts_path=tts_path,
                custom_speaker_id=None,  # TTS 已经生成了，这里不传
            )

            # Step 5: 写入 video 记录
            self._save_video_result(result)

            self._update_task(task_id, "completed", 100, "生成完成")
            logger.info("task=%s 生产完成", task_id)

        except Exception as e:
            logger.error("task=%s 生产失败: %s", task_id, e)
            self._update_task(task_id, "failed", 0, error=str(e))

    # ------------------------------------------------------------------
    # 各步骤实现
    # ------------------------------------------------------------------

    def _get_script(self, script_id: Optional[int]) -> Optional[Script]:
        if not script_id:
            # 没指定就取项目第一个脚本
            return self.db.query(Script).filter(
                Script.project_id == self.project_id
            ).first()
        return self.db.query(Script).filter(
            Script.id == script_id,
            Script.project_id == self.project_id,
        ).first()

    def _generate_script(self, task_id: int) -> Optional[Script]:
        """调用现有文案生成能力 (AIExpertService.script_expert) 生成并保存 Script。

        复用 ai_service.py 的 script_expert，不重新设计文案系统。
        选题取自项目 topic；生成失败返回 None（由调用方决定降级/报错）。
        """
        project = self.db.query(ContentProject).filter(
            ContentProject.id == self.project_id
        ).first()
        topic = project.topic if project else None
        if not topic:
            logger.warning("task=%s 无法生成文案: 项目 %s 缺少 topic", task_id, self.project_id)
            return None
        try:
            from app.experts.ai_expert import AIExpertService
            ai_result = AIExpertService().script_expert(topic, {})
            # AI 不可用时 ai_expert 会降级返回写死的模板文案（只替换 topic）。
            # 交付这种文案等于骗用户：每条视频的口播内容都一样。
            # 宁可明确失败让用户重试，也不要产出一条无法使用的成片。
            if ai_result.get("_degraded"):
                reason = ai_result.get("_degraded_reason") or "AI 服务不可用"
                logger.error("task=%s 文案生成降级为模板，拒绝使用: %s", task_id, reason)
                # 配额耗尽是最常见原因，且用户自己无法通过重试解决，
                # 必须直说而不是给一句含糊的"服务不可用"。
                if "quota" in reason.lower():
                    raise ScriptDegradedError(
                        "文案生成失败：AI 服务配额已用尽，无法实时创作文案。"
                        "请充值/升级方舟套餐，或等待配额重置后重试。"
                    )
                raise ScriptDegradedError(
                    f"文案生成失败：AI 服务暂时不可用（{reason}）。"
                    "请稍后重试；若持续失败请检查 AI 配额与配置。"
                )
            content = ai_result.get("story_version") or ai_result.get("knowledge_version")
            if not content:
                logger.warning("task=%s 文案生成返回空: %s", task_id, ai_result.get("error"))
                return None
            score = None
            sc = ai_result.get("score")
            if isinstance(sc, dict):
                score = sc.get("total")
            script = Script(
                project_id=self.project_id,
                type="story",
                content=content,
                version=1,
                score=score,
            )
            self.db.add(script)
            self.db.commit()
            self.db.refresh(script)
            logger.info("task=%s 生成文案成功 script_id=%s topic=%s", task_id, script.id, topic)
            return script
        except ScriptDegradedError:
            # 明确的业务失败（AI 降级为模板），必须上抛让任务失败并告知用户，
            # 不能被这里的兜底 except 吞成 None 而后续静默继续。
            raise
        except Exception as e:
            logger.error("task=%s 文案生成异常: %s", task_id, e)
            return None

    def _generate_tts(self, text: str, voice_profile_id: Optional[int],
                      footage_path: Optional[Path] = None) -> Optional[Path]:
        """生成 TTS 配音，返回 mp3 路径"""
        from app.services.voice_clone import synthesize

        # 大模型会按 prompt 里的结构要求输出【黄金开头】【故事】这类段落标记，
        # 它们是给编剧看的骨架，不该被念出来（实测会被 TTS 逐字读成"黄金开头"）。
        text = _strip_structure_markers(text)

        output_dir = self.storage_root / "storage" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"tts_{self.project_id}_{int(time.time())}.mp3"

        custom_speaker_id = None
        if voice_profile_id:
            from app.models.voice_profile import UserVoiceProfile
            vp = self.db.query(UserVoiceProfile).filter(
                UserVoiceProfile.id == voice_profile_id,
                UserVoiceProfile.user_id == self.user_id,
                UserVoiceProfile.status == "active",
            ).first()
            if vp:
                custom_speaker_id = vp.custom_speaker_id

        # 本地 CosyVoice2 zero-shot 克隆需要一段参考音频 + 其逐字稿。
        # 声纹档案里没有可用样本时（存量用户多是这种情况），直接从本次要用的
        # 素材里截一段人声——音色天然匹配，也不必让用户重新录音。
        #
        # 注意：只在这里做"截取"，不做转写。逐字稿必须由 worker 侧用 whisper
        # 生成——生产机没有 whisper 也没有 GPU，在这里转写会静默失败并留下
        # 空文稿，而空文稿会让 zero-shot 克隆按错误的音素映射发音，
        # 产出整段无法辨识的声音（已实际发生过一次）。
        ref_audio, ref_text = None, None
        if footage_path:
            try:
                from app.services import local_tts
                ref_dir = self.storage_root / "storage" / "tmp" / "tts_ref"
                ref_audio = local_tts.extract_reference(
                    footage_path, ref_dir / f"ref_{self.project_id}.wav",
                    start=local_tts.TTS_REF_START, duration=local_tts.TTS_REF_DURATION)
                if ref_audio:
                    logger.info("[video_producer] 参考音频取自素材: %s（逐字稿由 worker 侧 ASR 生成）",
                                ref_audio.name)
            except Exception as e:
                logger.warning("[video_producer] 参考音频提取失败: %s", e)

        try:
            synthesize(
                db=self.db,
                custom_speaker_id=custom_speaker_id,
                text=text,
                output_path=out_path,
                profile_id=voice_profile_id,
                reference_audio=ref_audio,
                reference_text=ref_text,
            )
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path
        except Exception as e:
            logger.error("[video_producer] TTS 合成异常: %s", e)

        return None

    def _get_footage_path(self, footage_id: Optional[int]) -> Optional[Path]:
        if not footage_id:
            return None
        from app.models.footage import Footage
        footage = self.db.query(Footage).filter(
            Footage.id == footage_id,
            Footage.user_id == self.user_id,
        ).first()
        if not footage:
            return None
        # file_path 可能是 "storage/footage/xxx.mp4" 或绝对路径
        fp = Path(footage.file_path)
        if not fp.is_absolute():
            fp = self.storage_root / fp
        if fp.exists():
            return fp
        return None

    def _run_lipsync(self, video_path: Path, audio_path: Path) -> Optional[Path]:
        """调用口型同步服务，返回同步后的视频路径"""
        from app.services.lipsync_service import get_lipsync_service
        service = get_lipsync_service(self.storage_root)
        if not service.available:
            logger.warning("[video_producer] lipsync 不可用，跳过")
            return None

        result = service.sync_video(video_path, audio_path)
        return result

    def _render_video(
        self,
        script: str,
        footage_path: Path,
        tts_path: Path,
        custom_speaker_id: Optional[str],
    ) -> Dict[str, Any]:
        """调用 ffmpeg 渲染服务"""
        from app.services.video_renderer import render_video, _probe_video_meta
        from app.services.video_service import video_service

        # 构建简单的 plan：单段素材 + 自动字幕
        plan = video_service.build_composition_plan(
            script=script,
            footages=[{"id": 0, "file_path": str(footage_path),
                       "scene": "", "emotion": "", "topics": []}],
            voice_style="warm",
            emotion="calm",
        )

        # 时长对齐：scene 时长不超过素材（口型中间件/原素材）实际时长，
        # 否则脚本预估时长 > 素材时长时，渲染尾部无画面（黑屏/静帧），口型对不上
        meta = _probe_video_meta(footage_path)
        if meta and meta[2]:
            src_dur = max(1, int(meta[2]))
            for sc in plan.get("scene_plan", []):
                plan_dur = int(sc.get("duration") or src_dur)
                sc["duration"] = min(plan_dur, src_dur)

        result = render_video(
            plan=plan,
            project_id=self.project_id,
            user_id=self.user_id,
            storage_root=self.storage_root,
            tts_text=None,  # 已经生成好 tts_path，不需要再生成
            tts_audio_path=tts_path,
            custom_speaker_id=custom_speaker_id,
        )
        return result

    def _save_video_result(self, result: Dict[str, Any]):
        """保存渲染结果到 videos 表"""
        video = self.db.query(Video).filter(
            Video.project_id == self.project_id
        ).first()
        if video:
            video.status = "rendered"
            video.url = result.get("output_url")
            video.cover_url = result.get("cover_url")
            video.duration = int(result.get("duration", 0))
        else:
            video = Video(
                project_id=self.project_id,
                url=result.get("output_url"),
                cover_url=result.get("cover_url"),
                duration=int(result.get("duration", 0)),
                status="rendered",
                resolution="1080x1920",
            )
            self.db.add(video)

        # 同时把项目状态更新为 completed
        project = self.db.query(ContentProject).filter(
            ContentProject.id == self.project_id
        ).first()
        if project:
            project.status = "completed"
            project.workflow_status = "completed"

        self.db.commit()

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _get_task(self, task_id: int) -> Optional[WorkflowTask]:
        return self.db.query(WorkflowTask).filter(
            WorkflowTask.id == task_id
        ).first()

    def _update_task(
        self,
        task_id: int,
        status: str,
        progress: int,
        step_label: str = "",
        error: str = None,
    ):
        task = self._get_task(task_id)
        if not task:
            logger.warning("task=%s 不存在，无法更新状态/进度", task_id)
            return
        task.status = status
        task.progress = progress
        if error:
            task.error_message = error
        self.db.commit()
        if error:
            logger.error(
                "task=%s step=%s status=%s progress=%s 失败原因=%s",
                task_id, step_label, status, progress, error,
            )
        else:
            logger.info(
                "task=%s step=%s status=%s progress=%s",
                task_id, step_label, status, progress,
            )
