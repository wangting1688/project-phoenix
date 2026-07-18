"""
AI拍摄助手服务

核心原则：降低拍摄门槛，而不是提高创作标准

根据主播的拍摄能力画像，生成适合她的最低成本拍摄方案

三种主播模式：
A. 基础型（70-80%）：手机固定拍，一个背景，一个人讲话
B. 进阶型（20%）：有多个场景能力
C. 高级型（少量）：多场景、vlog、家庭故事
"""

from typing import Dict, Any, List, Optional
from app.core.database import SessionLocal
from app.models import CreatorProfile, CreatorAsset, VideoProject, VideoShot
from enum import Enum


class ShootingMode(str, Enum):
    """主播拍摄模式"""
    BASIC = "basic"       # 基础型：固定机位口播
    INTERMEDIATE = "intermediate"  # 进阶型：多场景
    ADVANCED = "advanced" # 高级型：vlog/故事


class ShootingAssistantService:
    """AI拍摄助手服务"""

    def __init__(self):
        self.db = SessionLocal()

    # ==================== 能力评估 ====================

    def evaluate_shooting_profile(self, user_id: int) -> Dict[str, Any]:
        """
        评估主播的拍摄能力，返回能力画像
        
        返回：
        {
            "shooting_level": "基础",
            "available_scenes": ["固定背景", "客厅"],
            "camera_skill": "低",
            "editing_skill": "低",
            "available_time": "每天30分钟",
            "recommended_mode": "basic"
        }
        """
        profile = self.db.query(CreatorProfile).filter(
            CreatorProfile.user_id == user_id
        ).first()

        # 如果已有拍摄能力画像，直接返回
        if profile and profile.shooting_profile:
            return profile.shooting_profile

        # 否则基于现有信息推断
        shooting_profile = self._infer_shooting_profile(profile)

        # 更新到数据库
        if profile:
            profile.shooting_profile = shooting_profile
            self.db.commit()

        return shooting_profile

    def _infer_shooting_profile(self, profile: Optional[CreatorProfile]) -> Dict[str, Any]:
        """基于主播画像推断拍摄能力"""
        result = {
            "shooting_level": "基础",
            "available_scenes": ["固定背景"],
            "camera_skill": "低",
            "editing_skill": "低",
            "available_time": "每天30分钟",
            "recommended_mode": "basic",
        }

        if not profile:
            return result

        # 根据年龄推断
        if profile.age and 30 <= profile.age <= 50:
            result["available_time"] = "每天30分钟"

        # 根据成长阶段推断
        if profile.growth_stage == "beginner":
            result["shooting_level"] = "基础"
            result["camera_skill"] = "低"
            result["editing_skill"] = "低"
        elif profile.growth_stage == "growth":
            result["shooting_level"] = "进阶"
            result["camera_skill"] = "中"
            result["editing_skill"] = "低"
        elif profile.growth_stage == "mature":
            result["shooting_level"] = "高级"
            result["camera_skill"] = "高"
            result["editing_skill"] = "中"

        # 根据编辑水平推断
        if profile.editing_level == "high":
            result["editing_skill"] = "高"
        elif profile.editing_level == "medium":
            result["editing_skill"] = "中"

        # 确定推荐模式
        if result["shooting_level"] == "基础":
            result["recommended_mode"] = "basic"
        elif result["shooting_level"] == "进阶":
            result["recommended_mode"] = "intermediate"
        else:
            result["recommended_mode"] = "advanced"

        return result

    def update_shooting_profile(self, user_id: int, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新主播拍摄能力画像"""
        profile = self.db.query(CreatorProfile).filter(
            CreatorProfile.user_id == user_id
        ).first()

        if profile:
            profile.shooting_profile = profile_data
            self.db.commit()

        return profile_data

    # ==================== 生成拍摄方案 ====================

    def generate_shooting_plan(
        self,
        user_id: int,
        project_id: int,
        script_content: str,
    ) -> Dict[str, Any]:
        """
        根据主播能力和文案，生成拍摄方案
        
        返回：
        {
            "recommended_mode": "basic",
            "mode_description": "单人口播模式",
            "required_shots": [...],  # 必须拍
            "optional_shots": [...],   # 可选增强
            "required_assets": [...],  # 需要的素材
            "estimated_time": "10分钟"
        }
        """
        # 获取主播能力画像
        shooting_profile = self.evaluate_shooting_profile(user_id)
        mode = shooting_profile["recommended_mode"]

        # 根据模式生成方案
        plan = {
            "recommended_mode": mode,
            "mode_description": self._get_mode_description(mode),
            "required_shots": [],
            "optional_shots": [],
            "required_assets": [],
            "estimated_time": self._get_estimated_time(mode),
            "shooting_profile": shooting_profile,
        }

        # 解析文案，生成分镜
        script_segments = self._parse_script(script_content)

        # 根据模式生成分镜
        if mode == "basic":
            plan["required_shots"] = self._generate_basic_shots(script_segments)
            plan["optional_shots"] = self._generate_basic_optional_shots(script_segments)
        elif mode == "intermediate":
            plan["required_shots"] = self._generate_intermediate_shots(script_segments)
            plan["optional_shots"] = self._generate_intermediate_optional_shots(script_segments)
        else:
            plan["required_shots"] = self._generate_advanced_shots(script_segments)
            plan["optional_shots"] = self._generate_advanced_optional_shots(script_segments)

        # 生成素材需求清单
        plan["required_assets"] = self._generate_asset_requirements(plan["required_shots"])
        plan["optional_assets"] = self._generate_asset_requirements(plan["optional_shots"])

        # 保存分镜到数据库
        self._save_shots(project_id, plan["required_shots"] + plan["optional_shots"])

        return plan

    def _get_mode_description(self, mode: str) -> str:
        """获取模式描述"""
        descriptions = {
            "basic": "单人口播模式 - 一个固定机位，一个干净背景",
            "intermediate": "进阶模式 - 可以增加生活场景素材",
            "advanced": "高级模式 - 支持多场景切换、故事叙述",
        }
        return descriptions.get(mode, "单人口播模式")

    def _get_estimated_time(self, mode: str) -> str:
        """获取预计拍摄时间"""
        times = {
            "basic": "10分钟",
            "intermediate": "20-30分钟",
            "advanced": "30-60分钟",
        }
        return times.get(mode, "10分钟")

    def _parse_script(self, script_content: str) -> List[Dict[str, Any]]:
        """解析文案，生成片段列表"""
        segments = []
        sentences = script_content.split("。")

        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue

            segment_type = "opening" if i == 0 else "body"
            if i == len(sentences) - 2:
                segment_type = "climax"
            elif i == len(sentences) - 1:
                segment_type = "ending"

            segments.append({
                "index": i + 1,
                "text": sentence + "。",
                "type": segment_type,
            })

        return segments

    # ==================== 基础模式分镜生成 ====================

    def _generate_basic_shots(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        基础模式：固定机位口播
        
        特点：一个背景，一个机位，靠字幕和包装提升质量
        """
        shots = []
        current_time = 0.0

        for i, segment in enumerate(segments):
            duration = len(segment["text"]) * 0.8  # 估算时长

            shot = {
                "shot_number": i + 1,
                "shot_type": "口播",
                "start_time": current_time,
                "end_time": current_time + duration,
                "description": "固定机位口播",
                "script_content": segment["text"],
                "action": self._get_basic_action(segment["type"]),
                "camera_angle": "正面",
                "background": "干净背景（白墙/书房）",
                "priority": "required",
            }

            shots.append(shot)
            current_time += duration

        return shots

    def _generate_basic_optional_shots(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基础模式可选增强：增加表情和动作变化"""
        shots = []
        current_time = 0.0

        for i, segment in enumerate(segments):
            if segment["type"] == "climax":
                duration = len(segment["text"]) * 0.8
                shots.append({
                    "shot_number": 100 + i,
                    "shot_type": "表情特写",
                    "start_time": current_time,
                    "end_time": current_time + duration,
                    "description": "增加表情变化，强化情绪",
                    "script_content": segment["text"],
                    "action": "表情变化（惊讶/认真）",
                    "camera_angle": "近景",
                    "priority": "optional",
                })

            current_time += len(segment["text"]) * 0.8

        return shots

    def _get_basic_action(self, segment_type: str) -> str:
        """获取基础动作指导"""
        actions = {
            "opening": "坐姿，表情自然，开始提问",
            "body": "保持坐姿，适当点头",
            "climax": "表情变化，稍微前倾",
            "ending": "微笑，引导互动",
        }
        return actions.get(segment_type, "自然讲述")

    # ==================== 进阶模式分镜生成 ====================

    def _generate_intermediate_shots(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        进阶模式：多场景能力
        
        在基础口播基础上，增加生活场景
        """
        shots = self._generate_basic_shots(segments)

        # 在高潮部分增加场景切换提示
        for shot in shots:
            if "climax" in shot.get("description", "") or shot.get("script_content", "").startswith("其实"):
                shot["description"] = shot["description"] + "（可切换场景）"

        return shots

    def _generate_intermediate_optional_shots(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """进阶模式可选：生活场景素材"""
        shots = []
        current_time = 0.0

        for i, segment in enumerate(segments):
            if segment["type"] in ["body", "climax"]:
                duration = len(segment["text"]) * 0.8
                
                # 根据内容推断场景
                scene = self._infer_scene(segment["text"])
                
                shots.append({
                    "shot_number": 100 + i,
                    "shot_type": "生活场景",
                    "start_time": current_time,
                    "end_time": current_time + duration,
                    "description": f"{scene}生活画面",
                    "script_content": segment["text"],
                    "action": "自然生活场景",
                    "background": scene,
                    "priority": "optional",
                })

            current_time += len(segment["text"]) * 0.8

        return shots

    def _infer_scene(self, text: str) -> str:
        """根据文案内容推断场景"""
        if "厨房" in text or "做饭" in text or "食材" in text:
            return "厨房"
        if "睡觉" in text or "睡眠" in text or "床" in text:
            return "卧室"
        if "散步" in text or "户外" in text or "运动" in text:
            return "户外"
        if "喝水" in text or "喝茶" in text:
            return "客厅"
        return "生活场景"

    # ==================== 高级模式分镜生成 ====================

    def _generate_advanced_shots(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        高级模式：多场景故事叙述
        
        适合有拍摄经验的主播
        """
        shots = []
        current_time = 0.0

        for i, segment in enumerate(segments):
            duration = len(segment["text"]) * 0.8

            if i == 0:
                # 开头：场景引入
                shots.append({
                    "shot_number": i + 1,
                    "shot_type": "场景引入",
                    "start_time": current_time,
                    "end_time": current_time + 3,
                    "description": "生活场景开场",
                    "script_content": "",
                    "action": "展示生活环境",
                    "camera_angle": "全景",
                    "priority": "required",
                })
                current_time += 3
                duration -= 3

            shots.append({
                "shot_number": i + 2,
                "shot_type": "口播",
                "start_time": current_time,
                "end_time": current_time + duration,
                "description": "多场景切换口播",
                "script_content": segment["text"],
                "action": self._get_basic_action(segment["type"]),
                "camera_angle": "正面/侧面交替",
                "background": "根据内容切换",
                "priority": "required",
            })

            current_time += duration

        return shots

    def _generate_advanced_optional_shots(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """高级模式可选：更多故事元素"""
        shots = []

        # 添加B-roll建议
        shots.append({
            "shot_number": 999,
            "shot_type": "B-roll",
            "start_time": 0,
            "end_time": 0,
            "description": "穿插生活细节B-roll",
            "script_content": "",
            "action": "日常活动细节",
            "priority": "enhancement",
        })

        return shots

    # ==================== 素材需求 ====================

    def _generate_asset_requirements(self, shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根据分镜生成素材需求清单"""
        requirements = []

        for shot in shots:
            if shot.get("priority") == "required":
                requirements.append({
                    "type": "creator",  # 主播真人素材
                    "role": shot.get("shot_type", "口播"),
                    "emotion": self._infer_emotion(shot.get("action", "")),
                    "duration": shot.get("end_time", 0) - shot.get("start_time", 0),
                })
            elif shot.get("priority") in ["optional", "enhancement"]:
                requirements.append({
                    "type": "b_roll",  # 辅助素材
                    "scene": shot.get("background", ""),
                    "duration": shot.get("end_time", 0) - shot.get("start_time", 0),
                })

        return requirements

    def _infer_emotion(self, action: str) -> str:
        """推断情绪"""
        if "惊讶" in action or "变化" in action:
            return "惊讶"
        if "认真" in action:
            return "认真"
        if "微笑" in action:
            return "开心"
        if "提问" in action:
            return "思考"
        return "自然"

    # ==================== 素材匹配 ====================

    def match_assets(
        self,
        user_id: int,
        requirements: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        根据需求清单匹配已有素材
        
        返回：
        {
            "matched": [...],     # 已有的素材
            "missing": [...],     # 缺少的素材
        }
        """
        matched = []
        missing = []

        for req in requirements:
            assets = self.db.query(CreatorAsset).filter(
                CreatorAsset.user_id == user_id,
                CreatorAsset.asset_role == req.get("type", "creator"),
            ).all()

            found = False
            for asset in assets:
                asset_emotion = asset.emotion or ""
                asset_scene = asset.scene or ""

                if (req.get("emotion") and asset_emotion == req["emotion"]) or \
                   (req.get("scene") and asset_scene == req["scene"]):
                    matched.append({
                        "requirement": req,
                        "asset": {
                            "id": asset.id,
                            "name": asset.name,
                            "url": asset.url,
                            "emotion": asset.emotion,
                            "scene": asset.scene,
                        },
                    })
                    found = True
                    break

            if not found:
                missing.append(req)

        return {
            "matched": matched,
            "missing": missing,
        }

    # ==================== 保存分镜 ====================

    def _save_shots(self, project_id: int, shots: List[Dict[str, Any]]) -> None:
        """保存分镜到数据库"""
        # 先删除旧的分镜
        self.db.query(VideoShot).filter(
            VideoShot.project_id == project_id
        ).delete()

        # 创建新分镜
        for shot_data in shots:
            shot = VideoShot(
                project_id=project_id,
                shot_number=shot_data["shot_number"],
                shot_type=shot_data["shot_type"],
                start_time=shot_data["start_time"],
                end_time=shot_data["end_time"],
                description=shot_data.get("description"),
                script_content=shot_data.get("script_content"),
                action=shot_data.get("action"),
                camera_angle=shot_data.get("camera_angle"),
                background=shot_data.get("background"),
                status="pending",
            )
            self.db.add(shot)

        self.db.commit()

    def close(self):
        self.db.close()