"""
AI素材分析服务

分析素材内容，生成AI可理解的标签和评分
"""

import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.database import SessionLocal
from app.models import CreatorAsset, AssetIntelligence, AssetAnalysisTask
from app.services.asset_scoring_service import AssetScoringService


class AssetAnalysisService:
    """AI素材分析服务"""

    def __init__(self):
        self.db = SessionLocal()
        self.scoring_service = AssetScoringService()

    def create_analysis_task(
        self,
        asset_id: int,
        user_id: int,
        priority: int = 0,
        analysis_types: Optional[List[str]] = None,
    ) -> AssetAnalysisTask:
        """创建素材分析任务"""
        if not analysis_types:
            analysis_types = ["face", "emotion", "scene", "speech"]

        task = AssetAnalysisTask(
            asset_id=asset_id,
            user_id=user_id,
            status="pending",
            priority=priority,
            analysis_types=analysis_types,
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        return task

    def analyze_asset(self, asset_id: int) -> AssetIntelligence:
        """
        分析单个素材
        
        模拟AI分析过程，生成完整的智能分析数据
        """
        asset = self.db.query(CreatorAsset).filter(
            CreatorAsset.id == asset_id
        ).first()

        if not asset:
            raise ValueError(f"素材不存在: {asset_id}")

        # 检查是否已有分析结果
        existing = self.db.query(AssetIntelligence).filter(
            AssetIntelligence.asset_id == asset_id
        ).first()

        if existing and existing.analysis_status == "completed":
            return existing

        # 模拟AI分析过程
        intelligence = self._perform_analysis(asset)

        self.db.add(intelligence)
        self.db.commit()
        self.db.refresh(intelligence)

        # 计算并更新评分
        intelligence.overall_score = self.scoring_service.calculate_score(intelligence)
        self.db.commit()

        return intelligence

    def _perform_analysis(self, asset: CreatorAsset) -> AssetIntelligence:
        """
        执行AI分析（模拟）
        
        实际项目中，这里会调用AI视觉分析API（如OpenAI Vision、百度AI等）
        """
        # 基于素材已有标签生成分析结果
        # 在实际项目中，这里是AI分析的真实结果

        intelligence = AssetIntelligence(
            asset_id=asset.id,
            user_id=asset.user_id,
            analysis_status="completed",
            duration=asset.duration or 0,
        )

        # 模拟画面质量分析
        intelligence.clarity_score = random.randint(70, 95)
        intelligence.lighting_score = random.randint(65, 90)
        intelligence.color_score = random.randint(60, 85)
        intelligence.composition_score = random.randint(70, 90)

        # 模拟人物分析
        intelligence.face_visibility = random.choice(["good", "good", "moderate"])
        intelligence.face_score = random.randint(75, 95)
        intelligence.eye_contact = random.choice(["strong", "strong", "moderate"])
        intelligence.person_count = 1
        intelligence.person_age_range = "40-50"
        intelligence.person_gender = "female"

        # 模拟情绪分析
        emotions = [
            ("亲切", "自然"),
            ("认真", "真诚"),
            ("开心", "亲切"),
            ("自然", "轻松"),
        ]
        primary, secondary = random.choice(emotions)
        intelligence.emotion_primary = primary
        intelligence.emotion_secondary = secondary
        intelligence.emotion_score = random.randint(75, 95)

        # 模拟场景分析
        scenes = ["固定背景", "客厅", "室内", "厨房", "户外"]
        intelligence.scene_type = asset.scene or random.choice(scenes)
        intelligence.scene_score = random.randint(70, 90)
        intelligence.background_cleanliness = random.choice(["high", "high", "medium"])

        # 模拟语音分析
        intelligence.speech_detected = True
        intelligence.speech_score = random.randint(70, 90)
        intelligence.voice_tone = random.choice(["warm", "warm", "professional"])
        intelligence.speech_pace = "normal"

        # 生成标签
        intelligence.style = random.choice(["可信赖", "亲切", "专业", "朋友聊天"])
        intelligence.topics = random.sample(
            ["健康", "养生", "家庭", "情感", "生活", "饮食", "运动"],
            k=random.randint(2, 4)
        )
        intelligence.tags = random.sample(
            ["可信赖", "40岁以上", "朋友聊天", "自然", "专业", "温暖", "亲切", "认真"],
            k=random.randint(3, 5)
        )

        # 模拟自动切片
        segments = self._generate_segments(asset.duration or 30)
        intelligence.segments = segments

        # 完整分析结果
        intelligence.analysis_result = {
            "analysis_time": datetime.now().isoformat(),
            "model_version": "v1.0",
            "confidence": random.uniform(0.8, 0.95),
            "summary": f"{intelligence.person_age_range}{intelligence.person_gender}性主播，"
                      f"表现{intelligence.emotion_primary}，"
                      f"适合{', '.join(intelligence.topics)}类内容",
        }

        return intelligence

    def _generate_segments(self, total_duration: float) -> List[Dict[str, Any]]:
        """生成素材片段（自动切片）"""
        segments = []
        num_segments = min(max(int(total_duration / 8), 2), 5)

        segment_types = [
            {"emotion": "微笑", "tags": ["开场", "亲和力"], "desc": "自然微笑开场"},
            {"emotion": "认真", "tags": ["知识讲解", "专业"], "desc": "认真讲解知识"},
            {"emotion": "亲切", "tags": ["互动", "信任"], "desc": "亲切互动"},
            {"emotion": "自然", "tags": ["过渡", "流畅"], "desc": "自然过渡"},
            {"emotion": "认真", "tags": ["总结", "结尾"], "desc": "认真总结"},
        ]

        for i in range(num_segments):
            start = i * (total_duration / num_segments)
            end = min(start + random.uniform(3, 8), total_duration)
            seg_type = segment_types[i % len(segment_types)]

            segments.append({
                "index": i + 1,
                "start": round(start, 1),
                "end": round(end, 1),
                "duration": round(end - start, 1),
                "score": random.randint(80, 98),
                "emotion": seg_type["emotion"],
                "tags": seg_type["tags"],
                "description": seg_type["desc"],
            })

        return segments

    def batch_analyze(self, user_id: int, asset_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """批量分析素材"""
        if not asset_ids:
            # 获取用户所有未分析的素材
            assets = self.db.query(CreatorAsset).filter(
                CreatorAsset.user_id == user_id,
            ).all()
            asset_ids = [a.id for a in assets]

        results = {
            "total": len(asset_ids),
            "completed": 0,
            "failed": 0,
            "details": [],
        }

        for asset_id in asset_ids:
            try:
                intelligence = self.analyze_asset(asset_id)
                results["completed"] += 1
                results["details"].append({
                    "asset_id": asset_id,
                    "status": "success",
                    "score": intelligence.overall_score,
                })
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "asset_id": asset_id,
                    "status": "failed",
                    "error": str(e),
                })

        return results

    def get_analysis_result(self, asset_id: int) -> Optional[AssetIntelligence]:
        """获取素材分析结果"""
        return self.db.query(AssetIntelligence).filter(
            AssetIntelligence.asset_id == asset_id
        ).first()

    def close(self):
        self.db.close()
