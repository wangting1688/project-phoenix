"""
AI素材搜索服务

智能搜索和匹配素材，为AI剪辑提供最佳素材推荐
"""

from typing import Dict, Any, List, Optional
from app.core.database import SessionLocal
from app.models import CreatorAsset, AssetIntelligence
from app.services.asset_scoring_service import AssetScoringService


class AssetSearchService:
    """AI素材搜索服务"""

    def __init__(self):
        self.db = SessionLocal()
        self.scoring_service = AssetScoringService()

    def search(
        self,
        user_id: int,
        query: Optional[str] = None,
        scene_type: Optional[str] = None,
        emotion: Optional[str] = None,
        style: Optional[str] = None,
        topics: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        min_score: int = 0,
        asset_role: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        搜索素材
        
        支持多种搜索条件，返回匹配度排序的结果
        """
        # 基础查询：获取用户已分析的素材
        query_obj = self.db.query(
            CreatorAsset, AssetIntelligence
        ).join(
            AssetIntelligence,
            CreatorAsset.id == AssetIntelligence.asset_id
        ).filter(
            CreatorAsset.user_id == user_id,
            AssetIntelligence.analysis_status == "completed",
        )

        # 应用过滤条件
        if scene_type:
            query_obj = query_obj.filter(
                AssetIntelligence.scene_type == scene_type
            )

        if emotion:
            query_obj = query_obj.filter(
                (AssetIntelligence.emotion_primary == emotion) |
                (AssetIntelligence.emotion_secondary == emotion)
            )

        if style:
            query_obj = query_obj.filter(
                AssetIntelligence.style == style
            )

        if asset_role:
            query_obj = query_obj.filter(
                CreatorAsset.asset_role == asset_role
            )

        if min_score > 0:
            query_obj = query_obj.filter(
                AssetIntelligence.overall_score >= min_score
            )

        # 执行查询
        results = query_obj.all()

        # 计算匹配度并排序
        scored_results = []
        for asset, intelligence in results:
            match_score = self._calculate_match_score(
                intelligence, query, topics, tags
            )

            if match_score > 0 or not (query or topics or tags):
                scored_results.append({
                    "asset": self._format_asset(asset),
                    "intelligence": self._format_intelligence(intelligence),
                    "match_score": match_score,
                    "overall_score": intelligence.overall_score,
                })

        # 按匹配度排序
        scored_results.sort(key=lambda x: x["match_score"], reverse=True)

        return scored_results[:limit]

    def _calculate_match_score(
        self,
        intelligence: AssetIntelligence,
        query: Optional[str],
        topics: Optional[List[str]],
        tags: Optional[List[str]],
    ) -> int:
        """计算匹配度分数"""
        score = 0

        # 文本查询匹配
        if query:
            query_lower = query.lower()
            searchable_text = " ".join([
                intelligence.emotion_primary or "",
                intelligence.emotion_secondary or "",
                intelligence.scene_type or "",
                intelligence.style or "",
            ]).lower()

            if query_lower in searchable_text:
                score += 50

            # 标签匹配
            all_tags = (intelligence.tags or []) + (intelligence.topics or [])
            for tag in all_tags:
                if query_lower in tag.lower():
                    score += 30

        # 主题匹配
        if topics:
            asset_topics = intelligence.topics or []
            matched = set(topics) & set(asset_topics)
            score += len(matched) * 25

        # 标签匹配
        if tags:
            asset_tags = intelligence.tags or []
            matched = set(tags) & set(asset_tags)
            score += len(matched) * 20

        # 基础分（确保有分析结果的素材有一定分数）
        score += intelligence.overall_score * 0.3

        return min(score, 100)

    def find_best_segments(
        self,
        user_id: int,
        requirements: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        为剪辑需求寻找最佳片段
        
        requirements: [
            {
                "shot_number": 1,
                "type": "开场",
                "needs": {
                    "emotion": "微笑",
                    "scene": "固定背景",
                    "duration": 5,
                }
            },
            ...
        ]
        
        返回：每个需求匹配的最佳片段
        """
        matches = []

        for req in requirements:
            needs = req.get("needs", {})

            # 搜索匹配的素材
            results = self.search(
                user_id=user_id,
                emotion=needs.get("emotion"),
                scene_type=needs.get("scene"),
                tags=needs.get("tags", []),
                min_score=60,
                limit=5,
            )

            # 在素材中查找最佳片段
            best_match = None
            best_segment = None

            for result in results:
                intelligence = result.get("intelligence", {})
                segments = intelligence.get("segments", [])

                # 找到最适合的片段
                for seg in segments:
                    # 检查时长要求
                    min_duration = needs.get("duration", 3)
                    if seg.get("duration", 0) < min_duration:
                        continue

                    # 检查情绪要求
                    if needs.get("emotion") and seg.get("emotion") != needs.get("emotion"):
                        continue

                    # 评分
                    seg_score = seg.get("score", 0)
                    if not best_segment or seg_score > best_segment.get("score", 0):
                        best_segment = seg
                        best_match = result

            matches.append({
                "requirement": req,
                "matched_asset": best_match,
                "matched_segment": best_segment,
            })

        return matches

    def smart_recommend(
        self,
        user_id: int,
        script_content: str,
        shot_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        基于文案内容智能推荐素材
        
        分析文案，推断需要的素材类型，然后搜索匹配
        """
        # 从文案推断需求
        inferred_needs = self._infer_needs_from_script(script_content, shot_type)

        # 搜索匹配素材
        results = self.search(
            user_id=user_id,
            emotion=inferred_needs.get("emotion"),
            topics=inferred_needs.get("topics"),
            tags=inferred_needs.get("tags"),
            min_score=50,
            limit=10,
        )

        # 添加推荐理由
        for result in results:
            result["recommend_reason"] = self._generate_recommend_reason(
                result, inferred_needs
            )

        return results

    def _infer_needs_from_script(
        self,
        script_content: str,
        shot_type: Optional[str],
    ) -> Dict[str, Any]:
        """从文案推断素材需求"""
        needs = {
            "emotion": None,
            "topics": [],
            "tags": [],
            "scene": None,
        }

        # 根据文案内容推断主题
        topic_keywords = {
            "健康": ["健康", "养生", "身体", "疲惫", "睡眠"],
            "饮食": ["饮食", "食物", "营养", "吃", "喝水"],
            "运动": ["运动", "锻炼", "散步", "活动"],
            "家庭": ["家庭", "孩子", "家人", "生活"],
            "情感": ["情感", "心情", "压力", "焦虑"],
        }

        for topic, keywords in topic_keywords.items():
            for keyword in keywords:
                if keyword in script_content:
                    needs["topics"].append(topic)
                    break

        # 根据文案推断情绪
        if any(word in script_content for word in ["为什么", "怎么办", "不知道"]):
            needs["emotion"] = "认真"
            needs["tags"].append("提问")
        elif any(word in script_content for word in ["其实", "真相", "关键"]):
            needs["emotion"] = "认真"
            needs["tags"].append("解释")
        elif any(word in script_content for word in ["开心", "好", "棒", "不错"]):
            needs["emotion"] = "开心"
            needs["tags"].append("积极")
        else:
            needs["emotion"] = "自然"
            needs["tags"].append("讲述")

        # 根据镜头类型推断场景
        if shot_type == "口播":
            needs["scene"] = "固定背景"
        elif shot_type == "生活场景":
            needs["scene"] = "客厅"

        return needs

    def _generate_recommend_reason(
        self,
        result: Dict[str, Any],
        needs: Dict[str, Any],
    ) -> str:
        """生成推荐理由"""
        intelligence = result.get("intelligence", {})
        reasons = []

        # 情绪匹配
        if needs.get("emotion") == intelligence.get("emotion_primary"):
            reasons.append(f"情绪匹配：{intelligence.get('emotion_primary')}")

        # 主题匹配
        matched_topics = set(needs.get("topics", [])) & set(intelligence.get("topics", []))
        if matched_topics:
            reasons.append(f"主题匹配：{', '.join(matched_topics)}")

        # 高质量
        if intelligence.get("overall_score", 0) > 85:
            reasons.append("高质量素材")

        # 高评分片段
        segments = intelligence.get("segments", [])
        if segments and max(s.get("score", 0) for s in segments) > 90:
            reasons.append("包含高分片段")

        return "；".join(reasons) if reasons else "综合匹配度较高"

    def _format_asset(self, asset: CreatorAsset) -> Dict[str, Any]:
        """格式化素材信息"""
        return {
            "id": asset.id,
            "name": asset.name,
            "type": asset.type,
            "asset_role": asset.asset_role,
            "url": asset.url,
            "duration": asset.duration,
            "scene": asset.scene,
            "emotion": asset.emotion,
            "tags": asset.tags,
        }

    def _format_intelligence(self, intelligence: AssetIntelligence) -> Dict[str, Any]:
        """格式化智能分析结果"""
        return {
            "overall_score": intelligence.overall_score,
            "quality_score": intelligence.quality_score,
            "emotion_primary": intelligence.emotion_primary,
            "emotion_secondary": intelligence.emotion_secondary,
            "scene_type": intelligence.scene_type,
            "style": intelligence.style,
            "topics": intelligence.topics,
            "tags": intelligence.tags,
            "segments": intelligence.segments,
            "face_visibility": intelligence.face_visibility,
            "eye_contact": intelligence.eye_contact,
            "speech_detected": intelligence.speech_detected,
            "analysis_result": intelligence.analysis_result,
        }

    def close(self):
        self.db.close()
