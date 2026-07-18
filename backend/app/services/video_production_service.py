"""
视频生产执行编排层服务

TASK-016.3B.0：AI视频生产执行编排层

核心服务：
1. ProductionExecutionService - 生产任务编排
2. VideoEditorAgent - AI剪辑执行Agent
3. 素材不足闭环机制
"""

from datetime import datetime
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import (
    VideoProductionJob,
    VideoTimeline,
    VideoVariant,
    ProductionBlockTask,
)
from app.models.video_edit_plan import VideoEditPlan, VideoEditSegment
from app.models.asset_segment import AssetSegment


class ProductionExecutionService:
    """视频生产执行服务"""

    STATUS_FLOW = [
        "pending",
        "timeline_generating",
        "material_matching",
        "editing",
        "subtitle",
        "bgm",
        "cover",
        "rendering",
        "completed",
        "blocked",
        "failed",
    ]

    PLATFORM_STRATEGIES = {
        "douyin": {"strategy": "traffic", "target_duration": 35},
        "wechat_video": {"strategy": "conversion", "target_duration": 60},
        "xiaohongshu": {"strategy": "content", "target_duration": 45},
        "kuaishou": {"strategy": "community", "target_duration": 40},
    }

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def create_production_job(
        self,
        user_id: int,
        title: str,
        source_plan_id: int = None,
        video_project_id: int = None,
        creator_id: int = None,
        product_id: int = None,
        target_platforms: List[str] = None,
        job_type: str = "short_video",
    ) -> VideoProductionJob:
        """创建生产任务"""
        job = VideoProductionJob(
            user_id=user_id,
            title=title,
            source_plan_id=source_plan_id,
            video_project_id=video_project_id,
            creator_id=creator_id,
            product_id=product_id,
            target_platforms=target_platforms or [],
            job_type=job_type,
            status="pending",
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: int) -> VideoProductionJob:
        """获取生产任务"""
        return self.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()

    def update_job_status(self, job_id: int, status: str) -> VideoProductionJob:
        """更新任务状态"""
        job = self.get_job(job_id)
        if job and status in self.STATUS_FLOW:
            job.status = status
            self.db.commit()
            self.db.refresh(job)
        return job

    def calculate_progress(self, job: VideoProductionJob) -> int:
        """计算任务进度"""
        steps = [
            ("timeline_generated", 15),
            ("material_matched", 25),
            ("subtitle_ready", 10),
            ("bgm_ready", 10),
            ("cover_ready", 10),
            ("rendering_done", 30),
        ]
        progress = 0
        for flag, weight in steps:
            if getattr(job, flag, False):
                progress += weight
        return min(progress, 100)

    def generate_timeline_from_plan(self, job_id: int) -> Dict[str, Any]:
        """从导演方案生成时间线"""
        job = self.get_job(job_id)
        if not job or not job.source_plan_id:
            return {"success": False, "error": "缺少导演方案"}

        plan = self.db.query(VideoEditPlan).filter(VideoEditPlan.id == job.source_plan_id).first()
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        segments = self.db.query(VideoEditSegment).filter(
            VideoEditSegment.edit_plan_id == job.source_plan_id
        ).order_by(VideoEditSegment.sequence).all()

        timeline_items = []
        current_time = 0.0

        for seq, segment in enumerate(segments):
            duration = segment.duration or 5.0
            timeline = VideoTimeline(
                production_job_id=job_id,
                sequence=seq,
                start_time=current_time,
                end_time=current_time + duration,
                content_type="video",
                source_type="asset_segment",
                role=segment.role,
                segment_type=segment.segment_type,
                effect_config=segment.effect_config,
                transition_config=segment.transition_config,
                subtitle_config=segment.subtitle_config,
                audio_config=segment.audio_config,
                original_segment_id=segment.id,
                status="pending",
            )
            self.db.add(timeline)
            timeline_items.append(timeline)
            current_time += duration

        job.timeline_generated = True
        job.total_duration = int(current_time)
        job.status = "timeline_generating"
        self.db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "timeline_count": len(timeline_items),
            "total_duration": job.total_duration,
        }

    def generate_variants(self, job_id: int, platforms: List[str] = None) -> Dict[str, Any]:
        """生成多平台版本"""
        job = self.get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        target_platforms = platforms or job.target_platforms or ["wechat_video"]
        variants = []

        for platform in target_platforms:
            strategy = self.PLATFORM_STRATEGIES.get(platform, {})
            variant = VideoVariant(
                production_job_id=job_id,
                platform=platform,
                strategy=strategy.get("strategy", "balanced"),
                target_duration=strategy.get("target_duration", 35),
                status="pending",
                variant_config={
                    "platform": platform,
                    "strategy": strategy.get("strategy"),
                    "target_duration": strategy.get("target_duration"),
                },
            )
            self.db.add(variant)
            variants.append(variant)

        job.variant_count = len(variants)
        self.db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "variant_count": len(variants),
            "variants": [v.id for v in variants],
        }


class VideoEditorAgent:
    """AI剪辑执行Agent"""

    MATERIAL_SEARCH_FIELDS = {
        "hook": ["role", "emotion", "camera_type"],
        "pain_point": ["role", "emotion"],
        "knowledge": ["role", "content_type"],
        "product": ["role", "product_id"],
        "conversion": ["role", "emotion"],
        "social_proof": ["role", "camera_type"],
    }

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def match_material_for_timeline(self, timeline_id: int) -> Dict[str, Any]:
        """为时间线匹配素材"""
        timeline = self.db.query(VideoTimeline).filter(VideoTimeline.id == timeline_id).first()
        if not timeline:
            return {"success": False, "error": "时间线不存在"}

        role = timeline.role or "general"
        required_duration = timeline.end_time - timeline.start_time

        query = self.db.query(AssetSegment).filter(
            AssetSegment.status == "processed",
            AssetSegment.segment_score >= 80,
        )

        if role in self.MATERIAL_SEARCH_FIELDS:
            for field in self.MATERIAL_SEARCH_FIELDS[role]:
                if field == "role" and role:
                    query = query.filter(AssetSegment.role == role)
                if field == "emotion" and timeline.effect_config:
                    emotion = timeline.effect_config.get("emotion")
                    if emotion:
                        query = query.filter(AssetSegment.emotion == emotion)
                if field == "camera_type" and timeline.effect_config:
                    camera_type = timeline.effect_config.get("camera_type")
                    if camera_type:
                        query = query.filter(AssetSegment.camera_type == camera_type)

        segments = query.order_by(AssetSegment.segment_score.desc()).limit(5).all()

        if not segments:
            timeline.status = "material_missing"
            timeline.material_found = False
            timeline.material_gap = required_duration
            self.db.commit()
            return {
                "success": False,
                "error": "未找到匹配素材",
                "timeline_id": timeline_id,
                "required_duration": required_duration,
            }

        best_segment = segments[0]
        segment_duration = best_segment.end_time - best_segment.start_time

        timeline.source_type = "asset_segment"
        timeline.source_id = best_segment.id
        timeline.material_found = True
        timeline.material_duration = segment_duration
        timeline.material_gap = max(0, required_duration - segment_duration)
        timeline.status = "material_matched"
        self.db.commit()

        return {
            "success": True,
            "timeline_id": timeline_id,
            "segment_id": best_segment.id,
            "segment_duration": segment_duration,
            "gap_duration": timeline.material_gap,
            "score": best_segment.segment_score,
        }

    def match_materials_for_job(self, job_id: int) -> Dict[str, Any]:
        """为整个任务匹配素材"""
        timelines = self.db.query(VideoTimeline).filter(
            VideoTimeline.production_job_id == job_id,
            VideoTimeline.status == "pending",
        ).all()

        results = []
        missing_count = 0
        gap_count = 0

        for timeline in timelines:
            result = self.match_material_for_timeline(timeline.id)
            results.append(result)
            if not result["success"]:
                missing_count += 1
            elif result.get("gap_duration", 0) > 0:
                gap_count += 1

        job = self.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()
        if job:
            if missing_count > 0:
                job.status = "blocked"
                job.blocked_reasons = [
                    f"缺少{missing_count}段素材",
                    f"{gap_count}段素材时长不足",
                ]
            else:
                job.material_matched = True
                job.status = "material_matching"
                job.progress = 25

            self.db.commit()

        return {
            "success": missing_count == 0,
            "job_id": job_id,
            "total_timelines": len(timelines),
            "matched_count": len(timelines) - missing_count,
            "missing_count": missing_count,
            "gap_count": gap_count,
            "results": results,
        }

    def generate_clip_project(self, job_id: int) -> Dict[str, Any]:
        """生成剪辑工程"""
        job = self.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()
        if not job:
            return {"success": False, "error": "任务不存在"}

        if job.status not in ["material_matching", "editing"]:
            return {"success": False, "error": "素材尚未匹配完成"}

        timelines = self.db.query(VideoTimeline).filter(
            VideoTimeline.production_job_id == job_id
        ).order_by(VideoTimeline.sequence).all()

        clip_project = {
            "job_id": job_id,
            "title": job.title,
            "total_duration": job.total_duration,
            "tracks": [],
        }

        video_track = {"track": "video", "layers": []}
        audio_track = {"track": "audio", "layers": []}
        subtitle_track = {"track": "subtitle", "layers": []}

        for timeline in timelines:
            video_layer = {
                "id": timeline.id,
                "start": timeline.start_time,
                "end": timeline.end_time,
                "source_type": timeline.source_type,
                "source_id": timeline.source_id,
                "role": timeline.role,
                "effects": timeline.effect_config or {},
                "transition": timeline.transition_config or {},
            }
            video_track["layers"].append(video_layer)

            if timeline.audio_config:
                audio_layer = {
                    "id": timeline.id,
                    "start": timeline.start_time,
                    "end": timeline.end_time,
                    "config": timeline.audio_config,
                }
                audio_track["layers"].append(audio_layer)

            if timeline.subtitle_config:
                subtitle_layer = {
                    "id": timeline.id,
                    "start": timeline.start_time,
                    "end": timeline.end_time,
                    "config": timeline.subtitle_config,
                }
                subtitle_track["layers"].append(subtitle_layer)

        clip_project["tracks"].append(video_track)
        clip_project["tracks"].append(audio_track)
        clip_project["tracks"].append(subtitle_track)

        job.status = "editing"
        self.db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "clip_project": clip_project,
            "track_count": len(clip_project["tracks"]),
        }


class ProductionBlockService:
    """生产阻塞服务 - 素材不足闭环机制"""

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def check_material_gaps(self, job_id: int) -> List[ProductionBlockTask]:
        """检查素材缺口"""
        timelines = self.db.query(VideoTimeline).filter(
            VideoTimeline.production_job_id == job_id,
            VideoTimeline.material_found == False,
        ).all()

        block_tasks = []
        for timeline in timelines:
            existing_task = self.db.query(ProductionBlockTask).filter(
                ProductionBlockTask.timeline_id == timeline.id,
                ProductionBlockTask.status == "pending",
            ).first()

            if not existing_task:
                gap = timeline.end_time - timeline.start_time
                priority = "high" if gap > 3 else "medium"

                task = ProductionBlockTask(
                    production_job_id=job_id,
                    timeline_id=timeline.id,
                    block_type="material_missing",
                    priority=priority,
                    status="pending",
                    required_content_type=timeline.role,
                    required_duration=gap,
                    available_duration=0,
                    gap_duration=gap,
                    target_role=timeline.role,
                    target_emotion=timeline.effect_config.get("emotion") if timeline.effect_config else None,
                    reason=f"缺少{timeline.role}素材，时长{gap:.1f}秒",
                    suggested_action=f"请拍摄{timeline.role}相关素材，建议时长{gap:.1f}秒",
                )
                self.db.add(task)
                block_tasks.append(task)

        self.db.commit()
        return block_tasks

    def resolve_block_task(self, task_id: int, collection_task_id: int = None) -> ProductionBlockTask:
        """解决阻塞任务"""
        task = self.db.query(ProductionBlockTask).filter(ProductionBlockTask.id == task_id).first()
        if not task:
            return None

        task.status = "resolved"
        task.collection_task_id = collection_task_id
        self.db.commit()

        return task

    def get_blocked_jobs(self, user_id: int = None) -> List[VideoProductionJob]:
        """获取阻塞中的任务"""
        query = self.db.query(VideoProductionJob).filter(VideoProductionJob.status == "blocked")
        if user_id:
            query = query.filter(VideoProductionJob.user_id == user_id)
        return query.all()
