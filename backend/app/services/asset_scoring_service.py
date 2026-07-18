"""
AI素材评分服务

素材价值评分 = 画面质量×25% + 人物表现×30% + 情绪感染力×20% + 内容适配度×15% + 原创价值×10%
"""

from typing import Dict, Any
from app.models.asset_intelligence import AssetIntelligence


class AssetScoringService:
    """AI素材评分服务"""

    # 评分权重配置
    WEIGHTS = {
        "visual_quality": 0.25,    # 画面质量
        "person_performance": 0.30,  # 人物表现
        "emotion_power": 0.20,      # 情绪感染力
        "content_match": 0.15,      # 内容适配度
        "originality": 0.10,        # 原创价值
    }

    def calculate_score(self, intelligence: AssetIntelligence) -> int:
        """
        计算素材综合评分
        
        返回: 0-100的整数
        """
        # 1. 画面质量评分 (0-100)
        visual_score = self._calculate_visual_score(intelligence)

        # 2. 人物表现评分 (0-100)
        person_score = self._calculate_person_score(intelligence)

        # 3. 情绪感染力评分 (0-100)
        emotion_score = self._calculate_emotion_score(intelligence)

        # 4. 内容适配度评分 (0-100)
        content_score = self._calculate_content_score(intelligence)

        # 5. 原创价值评分 (0-100)
        originality_score = self._calculate_originality_score(intelligence)

        # 加权计算总分
        total = (
            visual_score * self.WEIGHTS["visual_quality"] +
            person_score * self.WEIGHTS["person_performance"] +
            emotion_score * self.WEIGHTS["emotion_power"] +
            content_score * self.WEIGHTS["content_match"] +
            originality_score * self.WEIGHTS["originality"]
        )

        return round(total)

    def _calculate_visual_score(self, intelligence: AssetIntelligence) -> int:
        """计算画面质量评分"""
        scores = []

        # 清晰度权重 40%
        clarity = intelligence.clarity_score or 0
        scores.append(clarity * 0.4)

        # 光线权重 30%
        lighting = intelligence.lighting_score or 0
        scores.append(lighting * 0.3)

        # 色彩权重 15%
        color = intelligence.color_score or 0
        scores.append(color * 0.15)

        # 构图权重 15%
        composition = intelligence.composition_score or 0
        scores.append(composition * 0.15)

        return round(sum(scores))

    def _calculate_person_score(self, intelligence: AssetIntelligence) -> int:
        """计算人物表现评分"""
        scores = []

        # 面部可见度
        face_scores = {"good": 100, "moderate": 70, "poor": 40, "none": 0}
        face_score = face_scores.get(intelligence.face_visibility or "", 0)
        scores.append(face_score * 0.4)

        # 眼神交流
        eye_scores = {"strong": 100, "moderate": 70, "weak": 40, "none": 0}
        eye_score = eye_scores.get(intelligence.eye_contact or "", 0)
        scores.append(eye_score * 0.3)

        # 面部质量
        face_quality = intelligence.face_score or 0
        scores.append(face_quality * 0.2)

        # 背景干净度
        clean_scores = {"high": 100, "medium": 70, "low": 30}
        clean_score = clean_scores.get(intelligence.background_cleanliness or "", 50)
        scores.append(clean_score * 0.1)

        return round(sum(scores))

    def _calculate_emotion_score(self, intelligence: AssetIntelligence) -> int:
        """计算情绪感染力评分"""
        scores = []

        # 情绪表现力
        emotion_score = intelligence.emotion_score or 0
        scores.append(emotion_score * 0.5)

        # 主要情绪加分
        high_emotion = ["亲切", "热情", "真诚", "认真"]
        medium_emotion = ["自然", "轻松", "开心"]
        
        primary = intelligence.emotion_primary or ""
        if primary in high_emotion:
            scores.append(100 * 0.3)
        elif primary in medium_emotion:
            scores.append(80 * 0.3)
        else:
            scores.append(60 * 0.3)

        # 次要情绪补充
        secondary = intelligence.emotion_secondary or ""
        if secondary:
            scores.append(70 * 0.2)
        else:
            scores.append(40 * 0.2)

        return round(sum(scores))

    def _calculate_content_score(self, intelligence: AssetIntelligence) -> int:
        """计算内容适配度评分"""
        scores = []

        # 主题丰富度
        topics = intelligence.topics or []
        topic_score = min(len(topics) * 20, 100)  # 最多5个主题得满分
        scores.append(topic_score * 0.4)

        # 标签丰富度
        tags = intelligence.tags or []
        tag_score = min(len(tags) * 15, 100)  # 最多7个标签得满分
        scores.append(tag_score * 0.3)

        # 风格适配
        style_scores = {
            "可信赖": 100,
            "专业": 90,
            "亲切": 95,
            "自然": 85,
            "朋友聊天": 90,
        }
        style = intelligence.style or ""
        style_score = style_scores.get(style, 60)
        scores.append(style_score * 0.3)

        return round(sum(scores))

    def _calculate_originality_score(self, intelligence: AssetIntelligence) -> int:
        """计算原创价值评分"""
        scores = []

        # 语音原创性（真人讲话 > 其他）
        if intelligence.speech_detected:
            scores.append(100 * 0.4)
        else:
            scores.append(50 * 0.4)

        # 场景独特性
        unique_scenes = ["vlog", "真实生活", "工作场景"]
        common_scenes = ["固定背景", "客厅"]
        
        scene = intelligence.scene_type or ""
        if scene in unique_scenes:
            scores.append(100 * 0.3)
        elif scene in common_scenes:
            scores.append(70 * 0.3)
        else:
            scores.append(80 * 0.3)

        # 使用次数（越少越原创，但前提是好的）
        usage = intelligence.usage_count or 0
        if usage == 0:
            scores.append(100 * 0.3)
        elif usage < 5:
            scores.append(80 * 0.3)
        else:
            scores.append(60 * 0.3)

        return round(sum(scores))

    def get_score_breakdown(self, intelligence: AssetIntelligence) -> Dict[str, Any]:
        """获取评分详细分解"""
        return {
            "overall": self.calculate_score(intelligence),
            "dimensions": {
                "visual_quality": {
                    "score": self._calculate_visual_score(intelligence),
                    "weight": self.WEIGHTS["visual_quality"],
                    "weighted": round(self._calculate_visual_score(intelligence) * self.WEIGHTS["visual_quality"]),
                },
                "person_performance": {
                    "score": self._calculate_person_score(intelligence),
                    "weight": self.WEIGHTS["person_performance"],
                    "weighted": round(self._calculate_person_score(intelligence) * self.WEIGHTS["person_performance"]),
                },
                "emotion_power": {
                    "score": self._calculate_emotion_score(intelligence),
                    "weight": self.WEIGHTS["emotion_power"],
                    "weighted": round(self._calculate_emotion_score(intelligence) * self.WEIGHTS["emotion_power"]),
                },
                "content_match": {
                    "score": self._calculate_content_score(intelligence),
                    "weight": self.WEIGHTS["content_match"],
                    "weighted": round(self._calculate_content_score(intelligence) * self.WEIGHTS["content_match"]),
                },
                "originality": {
                    "score": self._calculate_originality_score(intelligence),
                    "weight": self.WEIGHTS["originality"],
                    "weighted": round(self._calculate_originality_score(intelligence) * self.WEIGHTS["originality"]),
                },
            },
        }
