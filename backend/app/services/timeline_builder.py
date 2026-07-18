"""
Timeline Builder - Phoenix时间线构建器

TASK-016.3B.2：AI生产执行引擎

核心职责：
1. 从导演方案和生产任务构建标准Timeline JSON
2. 支持多轨道（视频、音频、字幕）
3. 生成符合FFmpeg/Remotion执行的格式
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import VideoProductionJob, VideoTimeline, VideoVariant
from app.models.video_edit_plan import VideoEditPlan, VideoEditSegment
from app.models.asset_segment import AssetSegment


class TimelineBuilder:
    """时间线构建器"""

    PLATFORM_FORMATS = {
        "douyin": {"width": 1080, "height": 1920, "fps": 30, "duration_limit": 35},
        "wechat_video": {"width": 1080, "height": 1920, "fps": 30, "duration_limit": 60},
        "xiaohongshu": {"width": 1080, "height": 1440, "fps": 30, "duration_limit": 45},
        "kuaishou": {"width": 1080, "height": 1920, "fps": 30, "duration_limit": 40},
    }

    TRANSITION_TYPES = {
        "cut": {"type": "cut", "duration": 0},
        "fade": {"type": "fade", "duration": 0.5},
        "zoom": {"type": "zoom", "duration": 0.3},
        "slide": {"type": "slide", "duration": 0.4},
    }

    ROLE_GROWTH_GOALS = {
        "hook": "retain",
        "problem": "connect",
        "knowledge": "educate",
        "solution": "inspire",
        "social_proof": "trust",
        "conversion": "action",
        "general": "maintain",
    }

    ROLE_EMOTIONS = {
        "hook": "curiosity",
        "problem": "empathy",
        "knowledge": "interest",
        "solution": "hope",
        "social_proof": "confidence",
        "conversion": "desire",
        "general": "neutral",
    }

    ROLE_VIEWER_STATES = {
        "hook": {"before": "无预期", "after": "产生好奇"},
        "problem": {"before": "不知道问题", "after": "意识到问题"},
        "knowledge": {"before": "寻求答案", "after": "获得知识"},
        "solution": {"before": "困扰中", "after": "看到希望"},
        "social_proof": {"before": "犹豫怀疑", "after": "建立信任"},
        "conversion": {"before": "理性权衡", "after": "产生行动"},
        "general": {"before": "中性", "after": "中性"},
    }

    ROLE_RETENTION_FUNCTIONS = {
        "hook": "create_question",
        "problem": "create_identification",
        "knowledge": "deliver_value",
        "solution": "offer_hope",
        "social_proof": "build_credibility",
        "conversion": "create_urgency",
        "general": "maintain_attention",
    }

    ROLE_CREATOR_REQUIREMENTS = {
        "hook": {"expression": "serious", "energy": "high"},
        "problem": {"expression": "empathetic", "energy": "medium"},
        "knowledge": {"expression": "professional", "energy": "medium"},
        "solution": {"expression": "hopeful", "energy": "medium"},
        "social_proof": {"expression": "confident", "energy": "medium"},
        "conversion": {"expression": "confident", "energy": "high"},
        "general": {"expression": "natural", "energy": "medium"},
    }

    COMMERCIAL_ROLES = ["product", "conversion", "promotion", "cta"]

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def build_phoenix_timeline(self, job_id: int) -> Dict[str, Any]:
        """
        构建Phoenix Timeline JSON标准格式

        返回格式：
        {
            "duration": 60,
            "tracks": [
                {
                    "type": "video",
                    "segments": [...]
                },
                {
                    "type": "subtitle",
                    "style": "douyin_fast"
                },
                {
                    "type": "music",
                    "style": "warm"
                }
            ]
        }
        """
        job = self._get_job(job_id)
        if not job:
            return {"error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"error": "导演方案不存在"}

        timeline_items = self._get_timeline_items(job_id)
        variants = self._get_variants(job_id)

        platform = job.target_platforms[0] if job.target_platforms else "wechat_video"
        platform_format = self.PLATFORM_FORMATS.get(platform, self.PLATFORM_FORMATS["wechat_video"])

        timeline = {
            "version": "1.0",
            "job_id": job_id,
            "title": job.title,
            "platform": platform,
            "format": platform_format,
            "duration": job.total_duration or 60,
            "tracks": [],
        }

        video_track = self._build_video_track(timeline_items)
        audio_track = self._build_audio_track(timeline_items, plan)
        subtitle_track = self._build_subtitle_track(timeline_items, plan)
        effect_track = self._build_effect_track(timeline_items)

        if video_track["segments"]:
            timeline["tracks"].append(video_track)
        if audio_track["segments"]:
            timeline["tracks"].append(audio_track)
        if subtitle_track["segments"]:
            timeline["tracks"].append(subtitle_track)
        if effect_track["effects"]:
            timeline["tracks"].append(effect_track)

        for variant in variants:
            variant_config = self._build_variant_config(variant, timeline)
            timeline.setdefault("variants", []).append(variant_config)

        return timeline

    def _build_video_track(self, timeline_items: List[VideoTimeline]) -> Dict[str, Any]:
        """构建视频轨道"""
        segments = []

        for seq, item in enumerate(timeline_items):
            if item.content_type != "video":
                continue

            role = item.role or "general"
            is_commercial = role in self.COMMERCIAL_ROLES
            viewer_state = self.ROLE_VIEWER_STATES.get(role, {"before": "中性", "after": "中性"})
            emotion_config = item.effect_config or {}
            emotion_start = emotion_config.get("emotion_start", "neutral")
            emotion_end = emotion_config.get("emotion", self.ROLE_EMOTIONS.get(role, "neutral"))
            creator_requirement = self.ROLE_CREATOR_REQUIREMENTS.get(role, {"expression": "natural", "energy": "medium"})

            segment = {
                "id": item.id,
                "scene": seq + 1,
                "asset_id": item.source_id,
                "start": item.start_time,
                "end": item.end_time,
                "duration": item.end_time - item.start_time,
                "role": role,
                "segment_type": item.segment_type,
                "source_type": item.source_type,
                "effects": item.effect_config or {},
                "transition": self._get_transition(item.transition_config),
                "material_found": item.material_found,
                "material_duration": item.material_duration,
                "growth_metadata": {
                    "growth_role": role,
                    "purpose": role,
                    "viewer_state_before": viewer_state["before"],
                    "viewer_state_after": viewer_state["after"],
                    "emotion": {
                        "start": emotion_start,
                        "end": emotion_end,
                    },
                    "retention_function": self.ROLE_RETENTION_FUNCTIONS.get(role, "maintain_attention"),
                    "growth_goal": self.ROLE_GROWTH_GOALS.get(role, "maintain"),
                    "commercial_level": 1 if is_commercial else 0,
                    "commercial_pressure_score": self._calc_segment_commercial_pressure(item, role),
                    "attention_score": self._calculate_attention_score(item, seq),
                    "creator_requirement": creator_requirement,
                },
            }

            segments.append(segment)

        return {
            "type": "video",
            "segments": segments,
        }

    def _calc_segment_commercial_pressure(self, item: VideoTimeline, role: str) -> int:
        """计算单段商业压力"""
        if role in self.COMMERCIAL_ROLES:
            return 70
        effect_config = item.effect_config or {}
        if effect_config.get("has_product"):
            return 60
        if effect_config.get("has_brand"):
            return 50
        if effect_config.get("has_promotion"):
            return 80
        return 0

    def _calculate_attention_score(self, item: VideoTimeline, sequence: int) -> int:
        """计算注意力评分"""
        score = 50

        if sequence == 0:
            score += 30
        elif sequence == 1:
            score += 15

        role = item.role or "general"
        if role == "hook":
            score += 20
        elif role in ["problem", "knowledge"]:
            score += 10

        emotion_config = item.effect_config or {}
        emotion = emotion_config.get("emotion", "")
        high_attention_emotions = ["curiosity", "surprise", "excitement", "fear"]
        if emotion in high_attention_emotions:
            score += 15

        return min(100, score)

    def _build_audio_track(self, timeline_items: List[VideoTimeline], plan: VideoEditPlan) -> Dict[str, Any]:
        """构建音频轨道"""
        segments = []

        for item in timeline_items:
            if item.audio_config:
                segment = {
                    "id": item.id,
                    "start": item.start_time,
                    "end": item.end_time,
                    "config": item.audio_config,
                }
                segments.append(segment)

        bgm_config = plan.bgm_config or {}
        if bgm_config:
            segments.append({
                "id": "bgm",
                "start": 0,
                "end": plan.total_duration or 60,
                "type": "bgm",
                "style": bgm_config.get("style", "warm"),
                "volume": bgm_config.get("volume", 0.3),
                "fade_in": bgm_config.get("fade_in", 1.0),
                "fade_out": bgm_config.get("fade_out", 2.0),
            })

        return {
            "type": "audio",
            "segments": segments,
        }

    def _build_subtitle_track(self, timeline_items: List[VideoTimeline], plan: VideoEditPlan) -> Dict[str, Any]:
        """构建字幕轨道"""
        segments = []

        for item in timeline_items:
            if item.subtitle_config:
                segment = {
                    "id": item.id,
                    "start": item.start_time,
                    "end": item.end_time,
                    "config": item.subtitle_config,
                }
                segments.append(segment)

        subtitle_style = plan.subtitle_style or "default"
        platform_style_map = {
            "douyin": "pop",
            "wechat_video": "fade",
            "xiaohongshu": "elegant",
            "kuaishou": "bold",
        }

        return {
            "type": "subtitle",
            "style": subtitle_style,
            "platform_style": platform_style_map.get(plan.platform, "fade"),
            "segments": segments,
        }

    def _build_effect_track(self, timeline_items: List[VideoTimeline]) -> Dict[str, Any]:
        """构建特效轨道"""
        effects = []

        for item in timeline_items:
            if item.effect_config:
                effect = {
                    "id": item.id,
                    "start": item.start_time,
                    "end": item.end_time,
                    "type": item.effect_config.get("type", "none"),
                    "params": item.effect_config.get("params", {}),
                }
                effects.append(effect)

        return {
            "type": "effect",
            "effects": effects,
        }

    def _build_variant_config(self, variant: VideoVariant, base_timeline: Dict[str, Any]) -> Dict[str, Any]:
        """构建版本配置"""
        platform_format = self.PLATFORM_FORMATS.get(variant.platform, self.PLATFORM_FORMATS["wechat_video"])

        return {
            "id": variant.id,
            "platform": variant.platform,
            "strategy": variant.strategy,
            "target_duration": variant.target_duration,
            "format": platform_format,
            "config": variant.variant_config or {},
        }

    def _get_transition(self, transition_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取转场效果"""
        if not transition_config:
            return self.TRANSITION_TYPES["cut"]

        transition_type = transition_config.get("type", "cut")
        return self.TRANSITION_TYPES.get(transition_type, self.TRANSITION_TYPES["cut"])

    def _get_job(self, job_id: int):
        return self.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()

    def _get_plan(self, plan_id: int):
        if not plan_id:
            return None
        return self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()

    def _get_timeline_items(self, job_id: int):
        return self.db.query(VideoTimeline).filter(
            VideoTimeline.production_job_id == job_id
        ).order_by(VideoTimeline.sequence).all()

    def _get_variants(self, job_id: int):
        return self.db.query(VideoVariant).filter(
            VideoVariant.production_job_id == job_id
        ).all()

    def export_for_ffmpeg(self, timeline: Dict[str, Any]) -> Dict[str, Any]:
        """导出FFmpeg格式"""
        ffmpeg_config = {
            "input_files": [],
            "filters": [],
            "output": {
                "path": f"/tmp/output_{timeline['job_id']}.mp4",
                "codec": "libx264",
                "fps": timeline["format"]["fps"],
                "width": timeline["format"]["width"],
                "height": timeline["format"]["height"],
            },
        }

        for track in timeline.get("tracks", []):
            if track["type"] == "video":
                for segment in track["segments"]:
                    if segment.get("asset_id"):
                        ffmpeg_config["input_files"].append({
                            "path": f"/assets/{segment['asset_id']}.mp4",
                            "start": segment["start"],
                            "duration": segment["duration"],
                        })

            elif track["type"] == "audio":
                for segment in track["segments"]:
                    if segment.get("type") == "bgm":
                        ffmpeg_config["input_files"].append({
                            "path": f"/assets/bgm/{segment['style']}.mp3",
                            "volume": segment.get("volume", 0.3),
                        })

            elif track["type"] == "subtitle":
                ffmpeg_config["subtitle"] = {
                    "style": track["platform_style"],
                    "segments": track["segments"],
                }

        return ffmpeg_config

    def export_for_remotion(self, timeline: Dict[str, Any]) -> Dict[str, Any]:
        """导出Remotion格式"""
        remotion_config = {
            "width": timeline["format"]["width"],
            "height": timeline["format"]["height"],
            "fps": timeline["format"]["fps"],
            "durationInFrames": timeline["duration"] * timeline["format"]["fps"],
            "composition": {
                "id": f"phoenix_{timeline['job_id']}",
                "component": "VideoComposition",
                "props": {
                    "tracks": timeline["tracks"],
                },
            },
        }

        return remotion_config
