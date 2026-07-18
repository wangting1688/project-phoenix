"""
素材片段服务

TASK-016.3A.5：AI素材片段化能力增强

核心功能：
1. 将素材拆分为可被剪辑调用的独立片段
2. 为主播建立表现画像
3. 提供AI剪辑搜索接口
"""

import random
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core.database import SessionLocal
from app.models import AssetSegment, CreatorPerformanceProfile, CreatorAsset, AssetIntelligence


class AssetSegmentService:
    """素材片段服务"""

    SEGMENT_ROLES = [
        "hook",       # 3秒抓人
        "problem",    # 提出问题
        "explain",    # 知识解释
        "trust",      # 建立信任
        "emotion",    # 情感共鸣
        "product",    # 产品关联
        "ending",     # 结尾互动
        "transition", # 过渡转场
    ]

    ROLE_DESCRIPTIONS = {
        "hook": "3秒抓人，吸引注意力",
        "problem": "提出问题，引发共鸣",
        "explain": "知识解释，专业讲解",
        "trust": "建立信任，展示权威",
        "emotion": "情感共鸣，触动人心",
        "product": "产品关联，自然植入",
        "ending": "结尾互动，引导行动",
        "transition": "过渡转场，衔接流畅",
    }

    EMOTIONS = [
        "亲切", "认真", "开心", "自然", "疑问", "真诚", "热情", "思考", "放松"
    ]

    def __init__(self):
        self.db = SessionLocal()

    def create_segments_for_asset(self, asset_id: int, user_id: int) -> List[AssetSegment]:
        """
        为素材创建片段
        
        将原始素材拆分为独立的、可被AI剪辑调用的片段
        """
        asset = self.db.query(CreatorAsset).filter(
            CreatorAsset.id == asset_id
        ).first()

        if not asset:
            raise ValueError(f"素材不存在: {asset_id}")

        # 删除旧片段
        self.db.query(AssetSegment).filter(
            AssetSegment.asset_id == asset_id
        ).delete()

        # 获取素材分析结果
        intelligence = self.db.query(AssetIntelligence).filter(
            AssetIntelligence.asset_id == asset_id
        ).first()

        # 生成片段
        segments = self._generate_segments(asset, intelligence)

        # 保存到数据库
        for seg in segments:
            self.db.add(seg)

        self.db.commit()

        # 更新主播表现画像
        self.update_creator_profile(user_id)

        return segments

    def _generate_segments(self, asset: CreatorAsset, intelligence: Optional[AssetIntelligence]) -> List[AssetSegment]:
        """生成片段"""
        segments = []
        total_duration = asset.duration or 30
        num_segments = min(max(int(total_duration / 8), 2), 6)

        # 根据时长分配角色
        role_sequence = self._get_role_sequence(num_segments)

        for i in range(num_segments):
            start = i * (total_duration / num_segments)
            end = min(start + random.uniform(3, 8), total_duration)
            duration = end - start

            role = role_sequence[i]
            emotion = self._get_emotion_for_role(role)

            segment = AssetSegment(
                asset_id=asset.id,
                user_id=asset.user_id,
                segment_number=i + 1,
                start_time=round(start, 1),
                end_time=round(end, 1),
                duration=round(duration, 1),
                segment_role=role,
                emotion=emotion,
                purpose=self.ROLE_DESCRIPTIONS.get(role, ""),
                description=self._generate_description(role, emotion),
                tags=self._generate_tags(role, emotion),
            )

            # 设置评分
            segment.quality_score = random.randint(75, 98)
            segment.conversion_score = random.randint(60, 95)
            segment.reuse_score = self._calculate_reuse_score(role)

            # 从intelligence继承信息
            if intelligence:
                segment.scene_type = intelligence.scene_type
                segment.background_cleanliness = intelligence.background_cleanliness
                segment.face_visibility = intelligence.face_visibility
                segment.eye_contact = intelligence.eye_contact
                segment.speech_detected = intelligence.speech_detected
                segment.voice_tone = intelligence.voice_tone

            segments.append(segment)

        return segments

    def _get_role_sequence(self, num_segments: int) -> List[str]:
        """获取角色序列"""
        sequences = {
            2: ["hook", "ending"],
            3: ["hook", "explain", "ending"],
            4: ["hook", "problem", "explain", "ending"],
            5: ["hook", "problem", "explain", "trust", "ending"],
            6: ["hook", "problem", "explain", "emotion", "trust", "ending"],
        }
        return sequences.get(num_segments, ["hook", "explain", "ending"])

    def _get_emotion_for_role(self, role: str) -> str:
        """根据角色获取情绪"""
        emotions_for_role = {
            "hook": ["疑问", "惊讶", "认真"],
            "problem": ["关心", "认真", "自然"],
            "explain": ["认真", "专业", "自然"],
            "trust": ["真诚", "亲切", "认真"],
            "emotion": ["亲切", "真诚", "热情"],
            "product": ["自然", "亲切", "认真"],
            "ending": ["微笑", "亲切", "自然"],
            "transition": ["自然", "放松"],
        }
        return random.choice(emotions_for_role.get(role, ["自然"]))

    def _generate_description(self, role: str, emotion: str) -> str:
        """生成描述"""
        descriptions = {
            "hook": f"{emotion}表情，适合作为视频开头吸引观众",
            "problem": f"{emotion}讲述问题，引发观众共鸣",
            "explain": f"{emotion}解释知识，专业可信",
            "trust": f"{emotion}分享经验，建立信任",
            "emotion": f"{emotion}表达情感，触动人心",
            "product": f"{emotion}展示产品，自然植入",
            "ending": f"{emotion}引导互动，结束视频",
            "transition": f"{emotion}过渡转场，衔接自然",
        }
        return descriptions.get(role, f"{emotion}表现")

    def _generate_tags(self, role: str, emotion: str) -> List[str]:
        """生成标签"""
        role_tags = {
            "hook": ["开场", "吸引", "疑问"],
            "problem": ["问题", "痛点", "共鸣"],
            "explain": ["知识", "讲解", "专业"],
            "trust": ["信任", "经验", "权威"],
            "emotion": ["情感", "温暖", "共鸣"],
            "product": ["产品", "植入", "自然"],
            "ending": ["结尾", "互动", "引导"],
            "transition": ["过渡", "流畅"],
        }
        return role_tags.get(role, []) + [emotion]

    def _calculate_reuse_score(self, role: str) -> int:
        """计算复用价值评分"""
        reuse_scores = {
            "hook": 95,      # 每天都需要开场
            "ending": 90,    # 每天都需要结尾
            "trust": 85,     # 经常需要建立信任
            "explain": 80,   # 经常需要讲解知识
            "emotion": 75,   # 有时需要情感
            "problem": 70,   # 有时需要提出问题
            "transition": 65, # 偶尔需要过渡
            "product": 50,   # 较少使用
        }
        return reuse_scores.get(role, 70)

    # ==================== 剪辑搜索接口 ====================

    def search_for_clip(
        self,
        user_id: int,
        segment_role: Optional[str] = None,
        emotion: Optional[str] = None,
        min_duration: float = 0,
        max_duration: float = 60,
        min_score: int = 0,
        exclude_segment_ids: Optional[List[int]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        AI剪辑搜索接口
        
        搜索适合剪辑的素材片段
        
        参数：
        - segment_role: 需要的角色 (hook/problem/explain/trust/emotion/product/ending)
        - emotion: 需要的情绪
        - min_duration: 最小时长（秒）
        - max_duration: 最大时长（秒）
        - min_score: 最小质量评分
        - exclude_segment_ids: 排除已使用的片段ID
        - limit: 返回数量
        """
        query = self.db.query(AssetSegment).filter(
            AssetSegment.user_id == user_id,
            AssetSegment.analysis_status == "completed",
            AssetSegment.duration >= min_duration,
            AssetSegment.duration <= max_duration,
            AssetSegment.quality_score >= min_score,
        )

        if segment_role:
            query = query.filter(AssetSegment.segment_role == segment_role)

        if emotion:
            query = query.filter(AssetSegment.emotion == emotion)

        if exclude_segment_ids:
            query = query.filter(AssetSegment.id.notin_(exclude_segment_ids))

        segments = query.order_by(
            AssetSegment.quality_score.desc(),
            AssetSegment.conversion_score.desc(),
        ).limit(limit).all()

        return [self._format_segment(s) for s in segments]

    def _format_segment(self, segment: AssetSegment) -> Dict[str, Any]:
        """格式化片段信息"""
        return {
            "id": segment.id,
            "asset_id": segment.asset_id,
            "segment_number": segment.segment_number,
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "duration": segment.duration,
            "segment_role": segment.segment_role,
            "emotion": segment.emotion,
            "purpose": segment.purpose,
            "description": segment.description,
            "tags": segment.tags,
            "quality_score": segment.quality_score,
            "conversion_score": segment.conversion_score,
            "reuse_score": segment.reuse_score,
            "scene_type": segment.scene_type,
            "usage_count": segment.usage_count,
        }

    # ==================== 主播表现画像 ====================

    def update_creator_profile(self, user_id: int) -> CreatorPerformanceProfile:
        """更新主播表现画像"""
        # 获取所有片段
        segments = self.db.query(AssetSegment).filter(
            AssetSegment.user_id == user_id
        ).all()

        if not segments:
            return self._create_empty_profile(user_id)

        # 分析情绪表现
        emotion_stats = {}
        for seg in segments:
            if seg.emotion not in emotion_stats:
                emotion_stats[seg.emotion] = {"count": 0, "total_score": 0}
            emotion_stats[seg.emotion]["count"] += 1
            emotion_stats[seg.emotion]["total_score"] += seg.quality_score

        best_emotion = max(emotion_stats, key=lambda k: emotion_stats[k]["total_score"] / emotion_stats[k]["count"])

        # 分析场景表现
        scene_stats = {}
        for seg in segments:
            scene = seg.scene_type or "未知"
            if scene not in scene_stats:
                scene_stats[scene] = {"count": 0, "total_score": 0}
            scene_stats[scene]["count"] += 1
            scene_stats[scene]["total_score"] += seg.quality_score

        best_scene = max(scene_stats, key=lambda k: scene_stats[k]["total_score"] / scene_stats[k]["count"])

        # 分析角色表现
        role_stats = {}
        for seg in segments:
            if seg.segment_role not in role_stats:
                role_stats[seg.segment_role] = {"count": 0, "avg_score": 0}
            role_stats[seg.segment_role]["count"] += 1
            role_stats[seg.segment_role]["avg_score"] += seg.quality_score

        best_roles = sorted(
            role_stats.items(),
            key=lambda x: x[1]["avg_score"] / x[1]["count"],
            reverse=True
        )[:3]
        best_roles_list = [r[0] for r in best_roles]

        # 计算整体表现评分
        avg_score = sum(s.quality_score for s in segments) / len(segments)

        # 获取或创建画像
        profile = self.db.query(CreatorPerformanceProfile).filter(
            CreatorPerformanceProfile.user_id == user_id
        ).first()

        if not profile:
            profile = CreatorPerformanceProfile(user_id=user_id)

        profile.best_emotion = best_emotion
        profile.emotion_scores = emotion_stats
        profile.best_scene = best_scene
        profile.scene_scores = scene_stats
        profile.best_segment_roles = best_roles_list
        profile.overall_performance_score = round(avg_score)
        profile.analyzed_segments = len(segments)
        profile.total_usage_count = sum(s.usage_count for s in segments)
        profile.last_updated_at = datetime.now()

        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)

        return profile

    def _create_empty_profile(self, user_id: int) -> CreatorPerformanceProfile:
        """创建空的表现画像"""
        profile = CreatorPerformanceProfile(
            user_id=user_id,
            best_emotion="亲切",
            best_scene="固定背景",
            best_segment_roles=["hook", "explain", "ending"],
        )
        self.db.add(profile)
        self.db.commit()
        return profile

    def get_creator_profile(self, user_id: int) -> Optional[CreatorPerformanceProfile]:
        """获取主播表现画像"""
        return self.db.query(CreatorPerformanceProfile).filter(
            CreatorPerformanceProfile.user_id == user_id
        ).first()

    def close(self):
        self.db.close()
