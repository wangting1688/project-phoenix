"""
Production Executor Agent - AI生产执行引擎

TASK-016.3B.2：AI生产执行引擎

核心职责：
1. 读取导演方案，转换为机器执行计划
2. 自动调用工具（Whisper/LLM/视频理解/图片模型/FFmpeg）
3. 管理生产步骤状态和失败重试
4. 生成Phoenix Timeline JSON标准格式
"""

from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import VideoProductionJob, VideoProductionStep
from app.models.video_edit_plan import VideoEditPlan, VideoEditSegment
from app.services.agent_tool_gateway import AgentToolGateway
from app.services.timeline_builder import TimelineBuilder
from app.services.growth_quality_agent import GrowthQualityAgent


class ProductionExecutorAgent:
    """生产执行Agent"""

    PRODUCTION_STEPS = [
        {"step_type": "transcribe", "tool_name": "whisper_transcribe", "description": "语音转文字"},
        {"step_type": "video_analysis", "tool_name": "video_analysis", "description": "视频理解分析"},
        {"step_type": "asset_match", "tool_name": None, "description": "素材匹配"},
        {"step_type": "caption", "tool_name": "llm_completion", "description": "字幕生成"},
        {"step_type": "cover", "tool_name": "image_generate", "description": "封面生成"},
        {"step_type": "render", "tool_name": "ffmpeg_process", "description": "视频渲染"},
    ]

    JOB_STATUS_FLOW = [
        "planning",
        "processing",
        "rendering",
        "completed",
        "failed",
        "blocked",
    ]

    def __init__(self):
        self.db = SessionLocal()
        self.gateway = AgentToolGateway()
        self.timeline_builder = TimelineBuilder()

    def close(self):
        self.db.close()

    def initialize_job(self, job_id: int) -> Dict[str, Any]:
        """初始化生产任务"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        if job.status != "pending":
            return {"success": False, "error": f"任务当前状态: {job.status}"}

        self._create_production_steps(job_id)

        job.status = "planning"
        job.current_step = 0
        self.db.commit()
        self.db.refresh(job)

        return {"success": True, "job_id": job_id, "status": job.status}

    def _create_production_steps(self, job_id: int):
        """创建生产步骤"""
        existing_steps = self.db.query(VideoProductionStep).filter(
            VideoProductionStep.job_id == job_id
        ).count()
        if existing_steps > 0:
            return

        for seq, step_def in enumerate(self.PRODUCTION_STEPS):
            step = VideoProductionStep(
                job_id=job_id,
                sequence=seq,
                step_type=step_def["step_type"],
                tool_name=step_def["tool_name"],
                status="pending",
                max_retries=3,
            )
            self.db.add(step)

        self.db.commit()

    def execute_job(self, job_id: int, skip_quality_check: bool = False) -> Dict[str, Any]:
        """执行整个生产任务"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        if job.status == "completed":
            return {"success": True, "job_id": job_id, "status": "already_completed"}

        if job.status == "failed":
            return {"success": False, "error": "任务已失败，请重试"}

        if not skip_quality_check:
            quality_result = self._check_growth_quality(job_id)
            if not quality_result["success"]:
                return quality_result

            if not quality_result["can_produce"]:
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": "增长质量检测未通过",
                    "growth_score": quality_result["growth_score"],
                    "suggestions": quality_result["suggestions"],
                }

        job.status = "processing"
        self.db.commit()

        steps = self.db.query(VideoProductionStep).filter(
            VideoProductionStep.job_id == job_id
        ).order_by(VideoProductionStep.sequence).all()

        results = []

        for step in steps:
            if step.status == "completed":
                results.append({"step": step.step_type, "status": "skipped"})
                continue

            step_result = self.execute_step(job_id, step.sequence)
            results.append({"step": step.step_type, **step_result})

            if step_result.get("success") is False:
                job.status = "failed"
                self.db.commit()
                return {"success": False, "job_id": job_id, "error": step_result.get("error"), "results": results}

        job.status = "completed"
        job.finished_at = datetime.now()
        self.db.commit()

        return {"success": True, "job_id": job_id, "status": "completed", "results": results}

    def execute_step(self, job_id: int, sequence: int) -> Dict[str, Any]:
        """执行单个生产步骤"""
        step = self.db.query(VideoProductionStep).filter(
            VideoProductionStep.job_id == job_id,
            VideoProductionStep.sequence == sequence,
        ).first()

        if not step:
            return {"success": False, "error": "步骤不存在"}

        if step.retry_count >= step.max_retries:
            return {"success": False, "error": "达到最大重试次数"}

        step.status = "running"
        step.retry_count += 1
        step.started_at = datetime.now()
        self.db.commit()

        try:
            result = self._execute_step_logic(job_id, step)
            step.status = "completed"
            step.output_data = result.get("data")
            step.completed_at = datetime.now()
            self.db.commit()
            return {"success": True, "data": result.get("data")}

        except Exception as e:
            step.status = "failed"
            step.error_message = str(e)
            self.db.commit()

            if step.retry_count < step.max_retries:
                return {"success": False, "error": str(e), "retry_count": step.retry_count, "will_retry": True}
            return {"success": False, "error": str(e), "retry_count": step.retry_count, "will_retry": False}

    def _execute_step_logic(self, job_id: int, step: VideoProductionStep) -> Dict[str, Any]:
        """执行具体步骤逻辑"""
        step_type = step.step_type

        if step_type == "transcribe":
            return self._execute_transcribe(job_id, step)
        elif step_type == "video_analysis":
            return self._execute_video_analysis(job_id, step)
        elif step_type == "asset_match":
            return self._execute_asset_match(job_id, step)
        elif step_type == "caption":
            return self._execute_caption(job_id, step)
        elif step_type == "cover":
            return self._execute_cover(job_id, step)
        elif step_type == "render":
            return self._execute_render(job_id, step)
        else:
            return {"success": False, "error": f"未知步骤类型: {step_type}"}

    def _execute_transcribe(self, job_id: int, step: VideoProductionStep) -> Dict[str, Any]:
        """执行语音转文字"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        segments = self._get_segments(job.source_plan_id)
        video_paths = []

        for segment in segments:
            if segment.source_type == "asset_segment" and segment.source_id:
                video_paths.append(f"asset_{segment.source_id}")

        step.input_data = {"video_paths": video_paths}

        if not video_paths:
            return {"success": True, "data": {"transcriptions": [], "message": "无视频素材需要转录"}}

        try:
            result = self.gateway.call_tool(
                "whisper_transcribe",
                video_paths=video_paths,
                language="zh",
            )
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_video_analysis(self, job_id: int, step: VideoProductionStep) -> Dict[str, Any]:
        """执行视频理解分析"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        segments = self._get_segments(job.source_plan_id)
        video_paths = []

        for segment in segments:
            if segment.source_type == "asset_segment" and segment.source_id:
                video_paths.append(f"asset_{segment.source_id}")

        step.input_data = {"video_paths": video_paths}

        if not video_paths:
            return {"success": True, "data": {"analyses": [], "message": "无视频素材需要分析"}}

        try:
            results = []
            for video_path in video_paths:
                analysis = self.gateway.call_tool(
                    "video_analysis",
                    video_path=video_path,
                    analyze_type="scene_detection",
                )
                results.append(analysis)
            return {"success": True, "data": {"analyses": results}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_asset_match(self, job_id: int, step: VideoProductionStep) -> Dict[str, Any]:
        """执行素材匹配"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        timeline = self.timeline_builder.build_phoenix_timeline(job_id)
        step.input_data = {"job_id": job_id}
        step.output_data = timeline

        return {"success": True, "data": timeline}

    def _execute_caption(self, job_id: int, step: VideoProductionStep) -> Dict[str, Any]:
        """执行字幕生成"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        script_content = plan.script_content or "暂无文案"
        duration = plan.total_duration or 60

        step.input_data = {
            "script_content": script_content,
            "duration": duration,
            "platform": job.target_platforms[0] if job.target_platforms else "wechat_video",
        }

        try:
            strategy = self.gateway.generate_caption_strategy(
                raw_text=script_content,
                video_duration=duration,
                content_type=plan.template_type or "general",
                platform=job.target_platforms[0] if job.target_platforms else "wechat_video",
            )
            return {"success": True, "data": strategy}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_cover(self, job_id: int, step: VideoProductionStep) -> Dict[str, Any]:
        """执行封面生成"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        platform = job.target_platforms[0] if job.target_platforms else "wechat_video"

        step.input_data = {
            "product_name": plan.product_name or job.title,
            "product_category": plan.product_category or "general",
            "title": job.title,
            "platform": platform,
        }

        try:
            strategy = self.gateway.generate_cover_prompt(
                product_name=plan.product_name or job.title,
                product_category=plan.product_category or "general",
                creator_profile={},
                platform=platform,
                title=job.title,
            )

            prompt = strategy.get("prompt", "")
            if prompt:
                image_result = self.gateway.call_tool(
                    "image_generate",
                    prompt=prompt,
                    size="1080x1920",
                )
                strategy["image_result"] = image_result.get("data")

            return {"success": True, "data": strategy}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_render(self, job_id: int, step: VideoProductionStep) -> Dict[str, Any]:
        """执行视频渲染"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        timeline = self.timeline_builder.build_phoenix_timeline(job_id)

        step.input_data = {
            "timeline": timeline,
            "job_id": job_id,
        }

        try:
            render_result = self.gateway.call_tool(
                "ffmpeg_process",
                timeline=timeline,
                output_path=f"/tmp/output_{job_id}.mp4",
            )
            return {"success": True, "data": render_result.get("data")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_job_progress(self, job_id: int) -> Dict[str, Any]:
        """获取任务进度"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        steps = self.db.query(VideoProductionStep).filter(
            VideoProductionStep.job_id == job_id
        ).order_by(VideoProductionStep.sequence).all()

        completed_steps = [s for s in steps if s.status == "completed"]
        failed_steps = [s for s in steps if s.status == "failed"]

        progress = (len(completed_steps) / len(steps)) * 100 if steps else 0

        return {
            "success": True,
            "job_id": job_id,
            "status": job.status,
            "progress": round(progress),
            "total_steps": len(steps),
            "completed_steps": len(completed_steps),
            "failed_steps": len(failed_steps),
            "steps": [
                {
                    "sequence": s.sequence,
                    "step_type": s.step_type,
                    "status": s.status,
                    "retry_count": s.retry_count,
                }
                for s in steps
            ],
        }

    def retry_failed_step(self, job_id: int, sequence: int) -> Dict[str, Any]:
        """重试失败步骤"""
        step = self.db.query(VideoProductionStep).filter(
            VideoProductionStep.job_id == job_id,
            VideoProductionStep.sequence == sequence,
        ).first()

        if not step:
            return {"success": False, "error": "步骤不存在"}

        if step.status != "failed":
            return {"success": False, "error": "步骤未失败"}

        step.status = "pending"
        step.error_message = None
        self.db.commit()

        return self.execute_step(job_id, sequence)

    def _get_job(self, job_id: int):
        return self.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()

    def _get_plan(self, plan_id: int):
        if not plan_id:
            return None
        return self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()

    def _get_segments(self, plan_id: int):
        if not plan_id:
            return []
        return self.db.query(VideoEditSegment).filter(
            VideoEditSegment.edit_plan_id == plan_id
        ).order_by(VideoEditSegment.sequence).all()

    def generate_timeline_json(self, job_id: int) -> Dict[str, Any]:
        """生成Phoenix Timeline JSON标准格式"""
        return self.timeline_builder.build_phoenix_timeline(job_id)

    def _check_growth_quality(self, job_id: int) -> Dict[str, Any]:
        """增长质量检测 - 在生产前判断是否有爆款潜力"""
        quality_agent = GrowthQualityAgent()
        try:
            result = quality_agent.assess_growth_quality(job_id)
            return result
        finally:
            quality_agent.close()

    def check_growth_quality(self, job_id: int) -> Dict[str, Any]:
        """外部调用增长质量检测"""
        return self._check_growth_quality(job_id)
